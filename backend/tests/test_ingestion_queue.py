from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException, Request
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.api.admin.ingestion import (
    _IngestionAppState,
    _IngestionApplication,
    _execute_document_ingestion_with_timeout,
    _run_document_ingestion_task_in_subprocess,
    claim_next_pending_document,
    start_ingestion,
)
from app.api.schemas.ingestion import StartIngestionRequest
from app.api.system import get_ingestion_worker_status
from app.config.settings import Settings
from app.modules.documents.application.commands import (
    MarkDocumentFailedCommand,
    MarkDocumentReadyCommand,
)
from app.modules.documents.application.services import DocumentApplicationService
from app.modules.documents.domain.entities import Document
from app.modules.documents.domain.repository_interfaces import (
    DocumentRepositoryInterface,
)
from app.modules.knowledge_bases.domain.repository_interfaces import (
    KnowledgeBaseRepositoryInterface,
)


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


class _AdvisoryLockResult:
    def __init__(self, acquired):
        self.acquired = acquired

    def scalar_one(self):
        return self.acquired


class _AdvisoryLockSession:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.closed = False

    def execute(self, statement, parameters):
        assert "pg_try_advisory_xact_lock" in str(statement)
        assert parameters["document_id"] == "test-doc-id"
        return _AdvisoryLockResult(self.acquired)

    def close(self):
        self.closed = True


def test_claim_marks_pending_document_processing_with_skip_locked():
    document = SimpleNamespace(
        id=uuid4(),
        status="pending",
        ingestion_version=0,
        failure_reason="previous failure",
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session = _ClaimSession(document)

    claimed_job = claim_next_pending_document(lambda: session)

    assert claimed_job == (str(document.id), 1)
    assert session.skip_locked
    assert "FOR UPDATE SKIP LOCKED" in session.sql
    assert "documents.status" in session.sql
    assert session.committed
    assert session.closed
    assert document.status == "processing"
    assert document.ingestion_version == 1
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
        ingestion_version=1,
        failure_reason=None,
        updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    session = _ClaimSession(document)

    claimed_job = claim_next_pending_document(
        lambda: session,
        stale_after_minutes=15,
    )

    assert claimed_job == (str(document.id), 2)
    assert session.skip_locked
    assert session.committed
    assert session.closed
    assert document.status == "processing"
    assert document.ingestion_version == 2
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

        def is_alive(self):
            return self.alive

        def terminate(self):
            self.terminated = True
            self.alive = False

    fake_process = FakeProcess()

    class FakeContext:
        def Process(self, *args, **kwargs):
            _ = (args, kwargs)
            return fake_process

    calls = {}

    def fake_fail_mark(session_factory, document_id, reason, settings):
        _ = session_factory
        calls["failed"] = (document_id, str(reason), settings)

    def fake_get_context(*args, **kwargs):
        _ = (args, kwargs)
        return FakeContext()

    monkeypatch.setattr(
        "app.api.admin.ingestion.multiprocessing.get_context",
        fake_get_context,
    )
    monkeypatch.setattr(
        "app.api.admin.ingestion._mark_document_failed_and_log",
        fake_fail_mark,
    )

    settings = cast(Settings, SimpleNamespace(ingestion_timeout_seconds=5))
    app = _IngestionApplication(
        state=_IngestionAppState(
            settings=settings,
            session_factory=lambda: cast(Session, _AdvisoryLockSession()),
        )
    )

    try:
        _execute_document_ingestion_with_timeout(
            "test-doc-id",
            app,
            timeout_seconds=5,
            ingestion_version=1,
        )
    except TimeoutError:
        pass

    assert fake_process.started is True
    assert fake_process.terminated is True
    assert calls["failed"][0] == "test-doc-id"
    assert "timed out" in calls["failed"][1].lower()
    assert calls["failed"][2] == 1


def test_duplicate_execution_skips_subprocess_when_advisory_lock_is_held(
    monkeypatch,
):
    lock_session = _AdvisoryLockSession(acquired=False)
    settings = cast(Settings, SimpleNamespace(ingestion_timeout_seconds=5))
    app = _IngestionApplication(
        state=_IngestionAppState(
            settings=settings,
            session_factory=lambda: cast(Session, lock_session),
        )
    )

    def fail_if_started(*args, **kwargs):
        _ = (args, kwargs)
        raise AssertionError("A duplicate execution must not start a process.")

    monkeypatch.setattr(
        "app.api.admin.ingestion.multiprocessing.get_context",
        fail_if_started,
    )

    _execute_document_ingestion_with_timeout(
        "test-doc-id",
        app,
        timeout_seconds=5,
        ingestion_version=1,
    )

    assert lock_session.closed


def test_timeout_failure_marker_is_scoped_to_ingestion_version(monkeypatch):
    observed = {}

    class FakeSession:
        def execute(self, statement, parameters=None):
            _ = parameters
            observed["statement"] = statement
            return SimpleNamespace(rowcount=1)

        def commit(self):
            observed["committed"] = True

        def rollback(self):
            observed["rolled_back"] = True

        def close(self):
            observed["closed"] = True

    from app.api.admin.ingestion import _mark_document_failed_and_log

    _mark_document_failed_and_log(
        lambda: cast(Session, FakeSession()),
        str(uuid4()),
        "timeout",
        7,
    )

    assert observed["statement"] is not None
    assert "documents.ingestion_version" in str(observed["statement"])
    assert observed["committed"] is True
    assert observed["closed"] is True


def test_marking_failed_document_failed_again_is_idempotent():
    document_id = uuid4()
    now = datetime.now(timezone.utc)
    existing_document = Document(
        id=document_id,
        application_id=uuid4(),
        knowledge_base_id=uuid4(),
        title="Test document",
        description=None,
        source_type="file",
        source_uri=None,
        storage_path="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1,
        checksum_sha256=None,
        status="failed",
        failure_reason="First timeout",
        created_at=now,
        updated_at=now,
        ingestion_version=1,
        ready_version=None,
    )

    class FakeDocumentRepository:
        def get_by_id(self, requested_id):
            assert requested_id == str(document_id)
            return existing_document

        def update(self, **changes):
            return replace(
                existing_document,
                title=changes["title"],
                description=changes["description"],
                status=changes["status"],
                failure_reason=changes["failure_reason"],
            )

    service = DocumentApplicationService(
        document_repository=cast(
            DocumentRepositoryInterface,
            FakeDocumentRepository(),
        ),
        knowledge_base_repository=cast(
            KnowledgeBaseRepositoryInterface,
            object(),
        ),
    )

    result = service.mark_failed(
        MarkDocumentFailedCommand(
            document_id=str(document_id),
            failure_reason="Second timeout",
        )
    )

    assert result.status == "failed"
    assert result.failure_reason == "Second timeout"


def test_document_without_published_version_cannot_be_marked_ready():
    document_id = uuid4()
    now = datetime.now(timezone.utc)
    existing_document = Document(
        id=document_id,
        application_id=uuid4(),
        knowledge_base_id=uuid4(),
        title="Not yet indexed",
        description=None,
        source_type="file",
        source_uri=None,
        storage_path="test.pdf",
        mime_type="application/pdf",
        file_size_bytes=1,
        checksum_sha256=None,
        status="processing",
        failure_reason=None,
        created_at=now,
        updated_at=now,
        ingestion_version=1,
        ready_version=None,
    )

    class FakeDocumentRepository:
        def get_by_id(self, requested_id):
            assert requested_id == str(document_id)
            return existing_document

    service = DocumentApplicationService(
        document_repository=cast(
            DocumentRepositoryInterface,
            FakeDocumentRepository(),
        ),
        knowledge_base_repository=cast(
            KnowledgeBaseRepositoryInterface,
            object(),
        ),
    )

    with pytest.raises(Exception) as exc_info:
        service.mark_ready(
            MarkDocumentReadyCommand(document_id=str(document_id))
        )

    assert getattr(exc_info.value, "code", None) == "document_version_not_ready"


def test_subprocess_initializes_database_state_before_ingestion(monkeypatch):
    settings = SimpleNamespace(
        database=SimpleNamespace(url="postgresql://test")
    )
    factory = SimpleNamespace(kw={"bind": None})
    observed = {}

    monkeypatch.setattr(
        "app.config.settings.get_settings",
        lambda: settings,
    )

    def fake_session_factory(database_url):
        assert database_url == "postgresql://test"
        return factory

    monkeypatch.setattr(
        "app.infrastructure.db.session.create_session_factory",
        fake_session_factory,
    )
    monkeypatch.setattr(
        "app.api.admin.ingestion.run_document_ingestion_task",
        lambda document_id, application, *, ingestion_version: observed.update(
            document_id=document_id,
            settings=application.state.settings,
            session_factory=application.state.session_factory,
            ingestion_version=ingestion_version,
        ),
    )

    _run_document_ingestion_task_in_subprocess(
        "test-doc-id",
        ingestion_version=3,
    )

    assert observed == {
        "document_id": "test-doc-id",
        "settings": settings,
        "session_factory": factory,
        "ingestion_version": 3,
    }


def test_subprocess_reports_ingestion_failure(monkeypatch):
    settings = SimpleNamespace(
        database=SimpleNamespace(url="postgresql://test")
    )
    factory = SimpleNamespace(kw={"bind": None})
    reported = []

    class ResultQueue:
        def put(self, result):
            reported.append(result)

    monkeypatch.setattr(
        "app.config.settings.get_settings",
        lambda: settings,
    )
    monkeypatch.setattr(
        "app.infrastructure.db.session.create_session_factory",
        lambda database_url: factory,
    )

    def fail_ingestion(document_id, application, *, ingestion_version=None):
        _ = (document_id, application, ingestion_version)
        raise ValueError("parser failed")

    monkeypatch.setattr(
        "app.api.admin.ingestion.run_document_ingestion_task",
        fail_ingestion,
    )

    with pytest.raises(ValueError, match="parser failed"):
        _run_document_ingestion_task_in_subprocess(
            "test-doc-id",
            cast(object, ResultQueue()),
        )

    assert reported == [("error", "parser failed")]


def test_start_ingestion_locks_document_and_rejects_already_queued(monkeypatch):
    document_id = uuid4()
    row = SimpleNamespace(status="pending")

    class StartSession:
        def __init__(self):
            self.closed = False
            self.rolled_back = False
            self.statement = ""

        def execute(self, statement):
            self.statement = str(statement.compile(dialect=postgresql.dialect()))
            return _ClaimResult(row)

        def rollback(self):
            self.rolled_back = True

        def close(self):
            self.closed = True

    session = StartSession()
    document_service = SimpleNamespace(
        get_by_id=lambda query: SimpleNamespace(status="pending"),
    )
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                session_factory=lambda: cast(Session, session),
                settings=SimpleNamespace(ingestion_stale_after_minutes=15),
            )
        )
    )
    monkeypatch.setattr(
        "app.api.admin.ingestion.get_document_application_service",
        lambda request, session: document_service,
    )

    with pytest.raises(HTTPException) as exc_info:
        start_ingestion(
            StartIngestionRequest(document_id=str(document_id)),
            cast(Request, request),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "document_ingestion_already_queued"
    assert "FOR UPDATE" in session.statement
    assert session.rolled_back
    assert session.closed


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

    assert get_ingestion_worker_status(cast(Request, request)) == {
        "worker_count": 2,
        "running_workers": 1,
        "healthy": False,
    }
