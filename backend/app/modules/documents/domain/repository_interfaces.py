from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.documents.domain.entities import Document
from uuid import UUID
from datetime import datetime

class DocumentRepositoryInterface(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, document_id: str) -> Document | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_knowledge_base_id(
        self,
        *,
        knowledge_base_id: UUID | str,
        status: str | None = None,
    ) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def list_by_status(self, *, status: str) -> list[Document]:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        *,
        document_id: str,
        title: str,
        description: str | None,
        status: str,
        failure_reason: str | None,
    ) -> Document:
        raise NotImplementedError

    @abstractmethod
    def delete(self, document_id: str) -> bool:
        raise NotImplementedError
