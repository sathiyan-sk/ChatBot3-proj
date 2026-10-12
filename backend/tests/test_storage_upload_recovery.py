from datetime import datetime, timezone
from io import BytesIO
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

from fastapi import UploadFile
import httpx
import pytest
from sqlalchemy.orm import Session
from app.config.settings import StorageSettings

from app.api.admin.storage_upload_recovery import (
    cleanup_stale_storage_upload_intents,
)
from app.api.admin.documents import upload_document
from app.config.settings import Settings
from app.core.exceptions import ApplicationError
from app.infrastructure.providers.storage.supabase_storage_provider import (
    SupabaseStorageProvider,
)


class _IntentResults:
    def __init__(self, intents):
        self.intents = intents

    def scalars(self):
        return self

    def all(self):
        return self.intents


class _Session:
    def __init__(self, intents, existing_document_id=None):
        self.intents = intents
        self.existing_document_id = existing_document_id
        self.deleted = []
        self.committed = False
        self.closed = False

    def execute(self, statement):
        if "storage_upload_intents" in str(statement):
            return _IntentResults(self.intents)
        return SimpleNamespace(
            scalar_one_or_none=lambda: self.existing_document_id
        )

    def delete(self, intent):
        self.deleted.append(intent)

    def commit(self):
        self.committed = True

    def rollback(self):
        raise AssertionError("cleanup should not need rollback")

    def close(self):
        self.closed = True


def test_stale_orphan_intent_deletes_storage_object_and_intent():
    intent = SimpleNamespace(
        id=uuid4(),
        storage_path="knowledge-base/document/source.pdf",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session = _Session([intent])
    deleted_paths = []
    storage = SimpleNamespace(delete=deleted_paths.append)

    cleaned = cleanup_stale_storage_upload_intents(
        lambda: cast(Session, session),
        storage,
        stale_after_minutes=1,
    )

    assert cleaned == 1
    assert deleted_paths == [intent.storage_path]
    assert session.deleted == [intent]
    assert session.committed
    assert session.closed


def test_stale_intent_for_committed_document_does_not_delete_object():
    intent = SimpleNamespace(
        id=uuid4(),
        storage_path="knowledge-base/document/source.pdf",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    session = _Session([intent], existing_document_id=uuid4())
    storage = SimpleNamespace(
        delete=lambda _path: (_ for _ in ()).throw(
            AssertionError("committed document source must be retained")
        )
    )

    cleaned = cleanup_stale_storage_upload_intents(
        lambda: cast(Session, session),
        storage,
        stale_after_minutes=1,
    )

    assert cleaned == 1
    assert session.deleted == [intent]
    assert session.committed
    assert session.closed


def test_upload_intent_and_document_are_committed_as_two_phase_saga():
    events = []
    application_id = uuid4()
    knowledge_base_id = uuid4()

    class UploadSession:
        def __init__(self):
            self.intent = None

        def add(self, intent):
            self.intent = intent
            events.append("intent_added")

        def commit(self):
            events.append("committed")

        def delete(self, intent):
            assert intent is self.intent
            events.append("intent_deleted")

    class UploadService:
        def upload(self, **kwargs):
            events.append("object_uploaded_and_document_created")
            document_id = kwargs["document_id"]
            return SimpleNamespace(
                id=document_id,
                application_id=application_id,
                knowledge_base_id=knowledge_base_id,
                title=kwargs["title"],
                description=kwargs["description"],
                source_type="file",
                source_uri=None,
                storage_path=(
                    f"{knowledge_base_id}/{document_id}/{kwargs['filename']}"
                ),
                mime_type=kwargs["content_type"],
                file_size_bytes=len(kwargs["content"]),
                checksum_sha256="checksum",
                status="pending",
                failure_reason=None,
                failure_code=None,
                ingestion_version=0,
                ready_version=None,
                ingestion_attempt_count=0,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

        def cleanup_uploaded_source(self, _storage_path):
            events.append("compensating_storage_delete")

    response = upload_document(
        knowledge_base_id=knowledge_base_id,
        title="Guide",
        description=None,
        file=UploadFile(
            filename="guide.txt",
            file=BytesIO(b"guide content"),
        ),
        service=cast(UploadService, UploadService()),
        settings=cast(
            Settings,
            SimpleNamespace(max_upload_file_size_bytes=1024),
        ),
        session=cast(Session, UploadSession()),
    )

    assert response.id is not None
    assert events == [
        "intent_added",
        "committed",
        "object_uploaded_and_document_created",
        "intent_deleted",
        "committed",
    ]


def test_supabase_delete_uses_remove_endpoint_and_json_prefix_for_unicode_path(
    monkeypatch,
):
    captured = {}

    def fake_delete(method, url, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured.update(kwargs)
        return httpx.Response(200, request=httpx.Request(method, url))

    monkeypatch.setattr(
        "app.infrastructure.providers.storage.supabase_storage_provider.httpx.request",
        fake_delete,
    )
    storage = SupabaseStorageProvider(
        settings=StorageSettings(
            supabase_url="https://storage.example",
            supabase_bucket_name="data_files",
            supabase_service_role_key="test-service-key",
            provider_timeout_seconds=10,
        )
    )
    storage_path = "kb/document/# Resume 🐛 (1).pdf"

    storage.delete(storage_path)

    assert captured["method"] == "DELETE"
    assert captured["url"] == (
        "https://storage.example/storage/v1/object/data_files"
    )
    assert captured["json"] == {"prefixes": [storage_path]}


def test_supabase_delete_reports_upstream_error_for_recovery_retry(monkeypatch):
    def fake_delete(method, url, **kwargs):
        _ = kwargs
        return httpx.Response(
            400,
            request=httpx.Request(method, url),
            json={"message": "bad request"},
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.storage.supabase_storage_provider.httpx.request",
        fake_delete,
    )
    storage = SupabaseStorageProvider(
        settings=StorageSettings(
            supabase_url="https://storage.example",
            supabase_bucket_name="data_files",
            supabase_service_role_key="test-service-key",
            provider_timeout_seconds=10,
        )
    )

    with pytest.raises(ApplicationError) as exc_info:
        storage.delete("kb/document/file.pdf")

    assert exc_info.value.code == "storage_delete_failed"
    assert exc_info.value.details == {"upstream_status": 400}


def test_supabase_delete_treats_missing_object_as_already_removed(monkeypatch):
    def fake_delete(method, url, **kwargs):
        _ = kwargs
        return httpx.Response(
            404,
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.storage.supabase_storage_provider.httpx.request",
        fake_delete,
    )
    storage = SupabaseStorageProvider(
        settings=StorageSettings(
            supabase_url="https://storage.example",
            supabase_bucket_name="data_files",
            supabase_service_role_key="test-service-key",
            provider_timeout_seconds=10,
        )
    )

    storage.delete("kb/document/already-gone.pdf")
