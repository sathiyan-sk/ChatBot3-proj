from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from sqlalchemy.dialects import postgresql

from app.api.admin.ingestion import (
    _execute_document_ingestion_with_timeout,
    claim_next_pending_document,
)
from app.api.system import get_ingestion_worker_status


class _ClaimResult:
    def __init__(self, document):
        self._document = document

    def scalar_one_or_none(self):
        return self._document


class _ClaimSession:
    def __init__(self, document):
        self.document = document
        self.committed = False
        self.closed = False
        self.skip_locked = False
        self.sql = ""

    def execute(self, statement):
        self.skip_locked = statement._for_update_arg.skip_locked
        self.sql = str(statement.compile(dialect=postgresql.dialect()))
        return _ClaimResult(self.document)

    def commit(self):
        self.committed = True

    def rollback(self):
        raise AssertionError("claim should not need rollback")

    def close(self):
        self.closed = True


def test_claim_marks_pending_document_processing_with_skip_locked():
    document = SimpleNamespace(
        id=uuid4(),
        status="pending",
        failure_reason="previous failure",
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session = _ClaimSession(document)

    document_id = claim_next_pending_document(lambda: session)

    assert document_id == str(document.id)
    assert session.skip_locked
    assert "FOR UPDATE SKIP LOCKED" in session.sql
    assert "documents.status" in session.sql
    assert session.committed
    assert session.closed
    assert document.status == "processing"
    assert document.failure_reason is None
    assert document.updated_at > datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_claim_returns_none_when_queue_is_empty():
    session = _ClaimSession(None)

    assert claim_next_pending_document(lambda: session) is None
    assert session.closed
    assert not session.committed


def test_claim_reclaims_expired_processing_document():
    document = SimpleNamespace(
        id=uuid4(),
        status="processing",
        failure_reason=None,
        updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    session = _ClaimSession(document)

    document_id = claim_next_pending_document(
        lambda: session,
        stale_after_minutes=15,
    )

    assert document_id == str(document.id)
    assert session.skip_locked
    assert session.committed
    assert session.closed
    assert document.status == "processing"
    assert document.updated_at > datetime(2020, 1, 1, tzinfo=timezone.utc)


def test_document_ingestion_timeout_terminates_hung_task(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.started = False
            self.terminated = False
            self.join_timeout = None
            self.alive = True

        def start(self):
            self.started = True

        def join(self, timeout=None):
            self.join_timeout = timeout
            self.alive = False

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True
            self.alive = False

    fake_process = FakeProcess()

    class FakeContext:
        def Process(self, *args, **kwargs):
            return fake_process

    calls = {}

    def fake_fail_mark(session_factory, document_id, exc):
        calls["failed"] = (document_id, str(exc))

    monkeypatch.setattr(
        "app.api.admin.ingestion.multiprocessing.get_context",
        lambda *args, **kwargs: FakeContext(),
    )
    monkeypatch.setattr(
        "app.api.admin.ingestion._mark_document_failed_and_log",
        fake_fail_mark,
    )

    app = SimpleNamespace(
        state=SimpleNamespace(
            settings=SimpleNamespace(ingestion_timeout_seconds=5),
            session_factory=lambda: object(),
        )
    )

    try:
        _execute_document_ingestion_with_timeout(
            "test-doc-id",
            app,
            timeout_seconds=5,
        )
    except TimeoutError:
        pass

    assert fake_process.started is True
    assert fake_process.terminated is True
    assert calls["failed"][0] == "test-doc-id"
    assert "timed out" in calls["failed"][1].lower()


def test_worker_health_endpoint_reports_running_and_failed_workers():
    class Worker:
        def __init__(self, is_done):
            self._is_done = is_done

        def done(self):
            return self._is_done

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                ingestion_workers=[Worker(False), Worker(True)]
            )
        )
    )

    assert get_ingestion_worker_status(request) == {
        "worker_count": 2,
        "running_workers": 1,
        "healthy": False,
    }
