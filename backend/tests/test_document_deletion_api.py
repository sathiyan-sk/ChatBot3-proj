from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.admin.documents import delete_document
from app.config.settings import Settings
from app.modules.documents.application.commands import DeleteDocumentCommand
from app.modules.documents.application.services import DocumentApplicationService


def test_delete_document_removes_vectors_and_row(monkeypatch):
    document_id = uuid4()
    calls = []

    class FakeVectorProvider:
        def __init__(self, *, settings, session):
            assert settings is test_settings
            assert session is test_session

        def delete_document_chunks(self, *, document_id):
            calls.append(("vectors", document_id))

    class FakeService:
        def get_by_id(self, _query):
            return SimpleNamespace(status="failed")

        def delete(self, command):
            assert isinstance(command, DeleteDocumentCommand)
            calls.append(("document", command.document_id))
            return True

    test_settings = SimpleNamespace()
    test_session = object()
    monkeypatch.setattr(
        "app.api.admin.documents.PgVectorProvider",
        FakeVectorProvider,
    )

    response = delete_document(
        document_id=document_id,
        session=cast(Session, test_session),
        settings=cast(Settings, test_settings),
        service=cast(DocumentApplicationService, FakeService()),
    )

    assert response.status_code == 204
    assert calls == [
        ("vectors", str(document_id)),
        ("document", str(document_id)),
    ]


def test_delete_document_rejects_active_ingestion(monkeypatch):
    class FakeService:
        def get_by_id(self, _query):
            return SimpleNamespace(status="processing")

    def unexpected_vector_provider(**_kwargs):
        raise AssertionError("active documents must not be deleted")

    monkeypatch.setattr(
        "app.api.admin.documents.PgVectorProvider",
        unexpected_vector_provider,
    )

    with pytest.raises(HTTPException) as error:
        delete_document(
            document_id=uuid4(),
            session=cast(Session, object()),
            settings=cast(Settings, SimpleNamespace()),
            service=cast(DocumentApplicationService, FakeService()),
        )

    assert error.value.status_code == 409
