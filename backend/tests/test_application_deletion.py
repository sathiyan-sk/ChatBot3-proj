from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.core.exceptions import ApplicationError
from app.modules.applications.application.deletion import (
    ApplicationDeletionService,
)


class _Result:
    def __init__(self, *, scalar=None, values=None):
        self._scalar = scalar
        self._values = values or []

    def scalar_one_or_none(self):
        return self._scalar

    def scalar_one(self):
        return self._scalar

    def scalars(self):
        return self

    def all(self):
        return self._values

    def __iter__(self):
        return iter(self._values)


class _Session:
    def __init__(self, application, documents, knowledge_base_ids, intents):
        self.application = application
        self.documents = documents
        self.knowledge_base_ids = knowledge_base_ids
        self.intents = intents
        self.events = []

    def execute(self, statement):
        sql = str(statement).lower()
        if sql.startswith("delete from applications"):
            self.events.append("delete_application")
            return SimpleNamespace(rowcount=1)
        if "count(" in sql:
            return _Result(scalar=1)
        if "from applications" in sql:
            return _Result(scalar=self.application)
        if "from documents" in sql:
            return _Result(values=self.documents)
        if "from knowledge_bases" in sql:
            return _Result(values=self.knowledge_base_ids)
        if "from storage_upload_intents" in sql:
            return _Result(values=self.intents)
        raise AssertionError(f"Unexpected statement: {sql}")

    def delete(self, value):
        self.events.append(("delete_upload_intent", value))

    def commit(self):
        self.events.append("commit")

    def rollback(self):
        self.events.append("rollback")


def _service(application, documents=None):
    knowledge_base_id = uuid4()
    session = _Session(
        application,
        documents or [],
        [knowledge_base_id],
        [
            SimpleNamespace(
                id=uuid4(),
                storage_path=f"{knowledge_base_id}/document/source.pdf",
                created_at=datetime.now(timezone.utc) - timedelta(hours=1),
            )
        ],
    )
    vector_calls = []
    storage_calls = []

    class _VectorProvider:
        def delete_knowledge_base_chunks(self, *, knowledge_base_id):
            vector_calls.append(knowledge_base_id)

        def count_knowledge_base_chunks(self, *, knowledge_base_id):
            _ = knowledge_base_id
            return 2

    class _StorageProvider:
        def delete_prefix(self, prefix):
            storage_calls.append(prefix)
            return 1

        def list_prefix(self, prefix):
            _ = prefix
            return ["file-1.pdf", "file-2.pdf"]

    service = ApplicationDeletionService(
        session=session,
        storage_provider=_StorageProvider(),
        vector_provider=_VectorProvider(),
    )
    return service, session, str(knowledge_base_id), vector_calls, storage_calls


def test_deletion_summary_counts_database_and_external_resources():
    application = SimpleNamespace(id=uuid4(), is_active=False)
    service, _session, _knowledge_base_id, _vectors, _storage = _service(
        application,
    )

    summary = service.get_deletion_summary(str(application.id))

    assert summary["documents"] == 1
    assert summary["stored_files"] == 2
    assert summary["indexed_chunks"] == 2
    assert summary["upload_intents"] == 1
    assert summary["processing_documents"] == 0
    assert summary["recent_uploads"] == 0


def test_permanent_delete_cleans_external_data_before_removing_application():
    application = SimpleNamespace(id=uuid4(), is_active=False)
    service, session, knowledge_base_id, vectors, storage = _service(application)

    service.delete_permanently(str(application.id))

    assert vectors == [knowledge_base_id]
    assert storage == [knowledge_base_id]
    assert session.events[-3:] == [
        ("delete_upload_intent", session.intents[0]),
        "delete_application",
        "commit",
    ]


def test_permanent_delete_requires_application_to_be_deactivated():
    application = SimpleNamespace(id=uuid4(), is_active=True)
    service, session, _knowledge_base_id, vectors, storage = _service(application)

    with pytest.raises(ApplicationError) as error:
        service.delete_permanently(str(application.id))

    assert error.value.code == "application_must_be_deactivated"
    assert vectors == []
    assert storage == []
    assert session.events == ["rollback"]


def test_permanent_delete_waits_for_document_ingestion_to_finish():
    application = SimpleNamespace(id=uuid4(), is_active=False)
    document = SimpleNamespace(status="processing", knowledge_base_id=uuid4())
    service, session, _knowledge_base_id, vectors, storage = _service(
        application,
        [document],
    )

    with pytest.raises(ApplicationError) as error:
        service.delete_permanently(str(application.id))

    assert error.value.code == "application_ingestion_in_progress"
    assert vectors == []
    assert storage == []
    assert session.events == ["rollback"]


def test_permanent_delete_waits_for_recent_file_upload_intents():
    application = SimpleNamespace(id=uuid4(), is_active=False)
    service, session, _knowledge_base_id, vectors, storage = _service(application)
    session.intents[0].created_at = datetime.now(timezone.utc)

    with pytest.raises(ApplicationError) as error:
        service.delete_permanently(str(application.id))

    assert error.value.code == "application_upload_in_progress"
    assert vectors == []
    assert storage == []
    assert session.events == ["rollback"]


def test_storage_cleanup_failure_keeps_database_records_for_retry():
    application = SimpleNamespace(id=uuid4(), is_active=False)
    service, session, _knowledge_base_id, vectors, _storage = _service(application)

    class _FailingStorage:
        def delete_prefix(self, _prefix):
            raise RuntimeError("storage unavailable")

    service._storage_provider = _FailingStorage()

    with pytest.raises(ApplicationError) as error:
        service.delete_permanently(str(application.id))

    assert error.value.code == "application_delete_failed"
    assert vectors
    assert "delete_application" not in session.events
    assert session.events[-1] == "rollback"
