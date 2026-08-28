from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid import UUID
from app.infrastructure.db.models.document_model import DocumentModel
from app.modules.documents.domain.entities import Document
from app.modules.documents.domain.repository_interfaces import DocumentRepositoryInterface
from app.modules.documents.infrastructure.mappers import map_document_model_to_entity

class SqlAlchemyDocumentRepository(DocumentRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self._session = session

    @staticmethod
    def _normalize_id(value: UUID | str) -> str:
        return str(value)

    def create(
        self,
        *,
        id: UUID | str,
        application_id: UUID | str,
        knowledge_base_id: UUID | str,
        title: str,
        description: str | None = None,
        source_type: str | None = None,
        source_uri: str | None = None,
        storage_path: str | None = None,
        mime_type: str | None = None,
        file_size_bytes: int | None = None,
        checksum_sha256: str | None = None,
        status: str | None = None,
        failure_reason: str | None = None,
    ) -> Document:
        model = DocumentModel(
            id=self._normalize_id(id),
            application_id=self._normalize_id(application_id),
            knowledge_base_id=self._normalize_id(knowledge_base_id),
            title=title,
            description=description,
            source_type=source_type,
            source_uri=source_uri,
            storage_path=storage_path,
            mime_type=mime_type,
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
            status=status,
            failure_reason=failure_reason,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return map_document_model_to_entity(model)

    def get_by_id(self, document_id: str) -> Document | None:
        normalized_document_id = self._normalize_id(document_id)
        statement = select(DocumentModel).where(DocumentModel.id == normalized_document_id)
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            return None
        return map_document_model_to_entity(model)

    def list_by_knowledge_base_id(
        self,
        *,
        knowledge_base_id: UUID | str,
        status: str | None = None,
    ) -> list[Document]:
        normalized_knowledge_base_id = self._normalize_id(knowledge_base_id)
        statement = (
            select(DocumentModel)
            .where(DocumentModel.knowledge_base_id == normalized_knowledge_base_id)
            .order_by(DocumentModel.created_at.desc())
        )
        if status is not None:
            statement = statement.where(DocumentModel.status == status)

        models = self._session.execute(statement).scalars().all()
        return [map_document_model_to_entity(model) for model in models]

    def list_by_status(self, *, status: str) -> list[Document]:
        statement = (
            select(DocumentModel)
            .where(DocumentModel.status == status)
            .order_by(DocumentModel.created_at.desc())
        )
        models = self._session.execute(statement).scalars().all()
        return [map_document_model_to_entity(model) for model in models]

    def update(
        self,
        *,
        document_id: str,
        title: str,
        description: str | None,
        status: str,
        failure_reason: str | None,
    ) -> Document:
        normalized_document_id = self._normalize_id(document_id)
        statement = select(DocumentModel).where(DocumentModel.id == normalized_document_id)
        model = self._session.execute(statement).scalar_one()
        model.title = title
        model.description = description
        model.status = status
        model.failure_reason = failure_reason
        self._session.flush()
        self._session.refresh(model)
        return map_document_model_to_entity(model)

    def delete(self, document_id: str) -> bool:
        normalized_document_id = self._normalize_id(document_id)
        statement = select(DocumentModel).where(DocumentModel.id == normalized_document_id)
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            return False
        self._session.delete(model)
        self._session.flush()
        return True
