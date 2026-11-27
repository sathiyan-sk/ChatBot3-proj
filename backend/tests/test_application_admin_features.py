from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.admin.applications import get_application_usage_summary
from app.api.admin.documents import update_website_refresh_schedule
from app.api.admin.ingestion import queue_due_website_refreshes
from app.api.admin.settings import validate_application_configuration
from app.api.schemas.documents import UpdateWebsiteRefreshScheduleRequest
from app.config.provider_registry import ProviderCatalog, ProviderModelOption


class _ScalarResult:
    def __init__(self, value):
        self.value = value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value


def test_usage_summary_reports_application_scoped_counts():
    class _Session:
        def __init__(self):
            self.count = 0
            self.closed = False

        def execute(self, statement):
            if "FROM applications" in str(statement):
                return _ScalarResult(uuid4())
            self.count += 1
            return _ScalarResult(self.count)

        def close(self):
            self.closed = True

    session = _Session()
    result = get_application_usage_summary(
        str(uuid4()),
        container=SimpleNamespace(session_factory=lambda: session),
    )

    assert result.conversations_total == 1
    assert result.conversations_recent == 2
    assert result.user_messages_recent == 3
    assert result.documents_total == 4
    assert result.documents_searchable == 5
    assert result.documents_processing == 6
    assert result.documents_failed == 7
    assert result.leads_total == 8
    assert result.feedback_total == 9
    assert session.closed


def test_configuration_validation_uses_enabled_provider_catalog():
    settings = SimpleNamespace(
        parser_provider="native",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        llm_provider="openai",
        llm_model="gpt-test",
    )
    catalog = ProviderCatalog(
        parsers=(ProviderModelOption("native", None, "Native"),),
        embeddings=(
            ProviderModelOption(
                "openai",
                "text-embedding-3-small",
                "Text Embedding",
                embedding_dimensions=1024,
            ),
        ),
        llms=(ProviderModelOption("openai", "gpt-test", "Test LLM"),),
    )
    service = SimpleNamespace(
        provider_catalog=catalog,
        get_by_application=lambda _query: settings,
    )

    result = validate_application_configuration("application-id", service)

    assert result.ready
    assert [check.capability for check in result.checks] == [
        "parser",
        "embedding",
        "llm",
    ]
    assert all(check.ready for check in result.checks)


def test_due_website_refresh_is_queued_and_next_run_scheduled():
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    document = SimpleNamespace(
        status="failed",
        failure_reason="previous failure",
        failure_code="ingestion_failed",
        ingestion_attempt_count=3,
        ingestion_next_attempt_at=now,
        ingestion_lease_expires_at=now,
        refresh_interval_hours=24,
        next_refresh_at=now - timedelta(minutes=1),
        updated_at=now - timedelta(days=1),
    )

    class _Rows:
        def scalars(self):
            return self

        def all(self):
            return [document]

    class _Session:
        def __init__(self):
            self.committed = False
            self.closed = False

        def execute(self, _statement):
            return _Rows()

        def commit(self):
            self.committed = True

        def rollback(self):
            raise AssertionError("unexpected rollback")

        def close(self):
            self.closed = True

    session = _Session()
    queued = queue_due_website_refreshes(
        lambda: session,
        now=now,
    )

    assert queued == 1
    assert document.status == "pending"
    assert document.failure_reason is None
    assert document.failure_code is None
    assert document.ingestion_attempt_count == 0
    assert document.ingestion_next_attempt_at is None
    assert document.ingestion_lease_expires_at is None
    assert document.next_refresh_at == now + timedelta(hours=24)
    assert document.updated_at == now
    assert session.committed
    assert session.closed


def test_website_refresh_schedule_can_be_disabled():
    document = SimpleNamespace(
        id=uuid4(),
        application_id=uuid4(),
        knowledge_base_id=uuid4(),
        title="Example",
        description=None,
        source_type="website",
        source_uri="https://example.com",
        storage_path=None,
        mime_type=None,
        file_size_bytes=None,
        checksum_sha256=None,
        status="ready",
        failure_reason=None,
        failure_code=None,
        ingestion_version=1,
        ready_version=1,
        ingestion_attempt_count=0,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        refresh_interval_hours=24,
        next_refresh_at=datetime.now(timezone.utc),
    )

    class _Session:
        def execute(self, _statement):
            return _ScalarResult(document)

    result = update_website_refresh_schedule(
        uuid4(),
        UpdateWebsiteRefreshScheduleRequest(refresh_interval_hours=None),
        session=_Session(),
    )

    assert result.refresh_interval_hours is None
    assert result.next_refresh_at is None


def test_refresh_schedule_rejects_non_website_documents():
    document = SimpleNamespace(source_type="file", status="ready")

    class _Session:
        def execute(self, _statement):
            return _ScalarResult(document)

    with pytest.raises(HTTPException) as error:
        update_website_refresh_schedule(
            uuid4(),
            UpdateWebsiteRefreshScheduleRequest(refresh_interval_hours=24),
            session=_Session(),
        )

    assert error.value.status_code == 422
