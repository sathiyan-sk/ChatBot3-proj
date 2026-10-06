from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from app.api.admin.ingestion import claim_next_pending_document


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

    def execute(self, statement):
        self.skip_locked = statement._for_update_arg.skip_locked
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
