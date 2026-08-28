from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID, uuid4
from typing import ClassVar
from app.core.exceptions import ApplicationError
from app.modules.documents.application.commands import (
    ArchiveDocumentCommand,
    CreateDocumentCommand,
    DeleteDocumentCommand,
    MarkDocumentFailedCommand,
    MarkDocumentProcessingCommand,
    MarkDocumentReadyCommand,
    UpdateDocumentCommand,
)
from app.modules.documents.application.dto import DocumentDto
from app.modules.documents.application.queries import (
    GetDocumentByIdQuery,
    ListDocumentsByKnowledgeBaseQuery,
    ListDocumentsByStatusQuery,
)
from app.modules.documents.domain.entities import Document
from app.modules.documents.domain.repository_interfaces import (
    DocumentRepositoryInterface,
)
from app.modules.documents.domain.value_objects import (
    DocumentSourceType,
    DocumentStatus,
    DocumentTitle,
)
from app.modules.knowledge_bases.domain.repository_interfaces import (
    KnowledgeBaseRepositoryInterface,
)


@dataclass(slots=True)
class DocumentApplicationService:
    document_repository: DocumentRepositoryInterface
    knowledge_base_repository: KnowledgeBaseRepositoryInterface
    storage_provider: object | None = None

    _ALLOWED_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "pending": {"processing", "failed", "archived"},
        "processing": {"ready", "failed", "archived"},
        "ready": {"archived", "processing"},
        "failed": {"processing", "archived"},
        "archived": set(),
    }
    def create(
        self,
        command: CreateDocumentCommand,
    ) -> DocumentDto:
        knowledge_base = (
            self.knowledge_base_repository.get_by_id(
                command.knowledge_base_id,
            )
        )

        if knowledge_base is None:
            raise ApplicationError(
                message="Knowledge base not found.",
                code="knowledge_base_not_found",
                status_code=404,
            )

        created = self.document_repository.create(
            id=uuid4(),
            application_id=knowledge_base.application_id,
            knowledge_base_id=knowledge_base.id,
            title=DocumentTitle(
                command.title,
            ).value,
            description=command.description,
            source_type=DocumentSourceType(
                command.source_type,
            ).value,
            source_uri=command.source_uri,
            storage_path=None,
            mime_type=None,
            file_size_bytes=None,
            checksum_sha256=None,
            status=DocumentStatus(
                "pending",
            ).value,
            failure_reason=None,
        )

        return self._to_dto(created)

    def upload(
        self,
        *,
        knowledge_base_id: UUID,
        title: str,
        description: str | None,
        filename: str,
        content_type: str | None,
        content: bytes,
    ) -> DocumentDto:
        knowledge_base = (
            self.knowledge_base_repository.get_by_id(
                knowledge_base_id,
            )
        )

        if knowledge_base is None:
            raise ApplicationError(
                message="Knowledge base not found.",
                code="knowledge_base_not_found",
                status_code=404,
            )

        if self.storage_provider is None:
            raise ApplicationError(
                message="Storage provider is not configured.",
                code="storage_provider_not_configured",
                status_code=500,
            )

        document_id = uuid4()
        storage_path = (
            f"{knowledge_base_id}/{document_id}/{filename}"
        )
        checksum_sha256 = hashlib.sha256(
            content,
        ).hexdigest()

        uploaded_path = self._upload_to_storage(
            path=storage_path,
            content=content,
            content_type=content_type,
        )

        created = self.document_repository.create(
            id=document_id,
            application_id=knowledge_base.application_id,
            knowledge_base_id=knowledge_base.id,
            title=DocumentTitle(title).value,
            description=description,
            source_type="file",
            source_uri=None,
            storage_path=uploaded_path,
            mime_type=content_type,
            file_size_bytes=len(content),
            checksum_sha256=checksum_sha256,
            status="pending",
            failure_reason=None,
        )

        return self._to_dto(created)

    def get_by_id(
        self,
        query: GetDocumentByIdQuery,
    ) -> DocumentDto:
        document = self.document_repository.get_by_id(
            query.document_id,
        )

        if document is None:
            raise ApplicationError(
                message="Document not found.",
                code="document_not_found",
                status_code=404,
            )

        return self._to_dto(document)

    def list_by_knowledge_base(
        self,
        query: ListDocumentsByKnowledgeBaseQuery,
    ) -> list[DocumentDto]:
        documents = (
            self.document_repository.list_by_knowledge_base_id(
                knowledge_base_id=query.knowledge_base_id,
                status=query.status,
            )
        )

        return [
            self._to_dto(document)
            for document in documents
        ]

    def list_by_status(
        self,
        query: ListDocumentsByStatusQuery,
    ) -> list[DocumentDto]:
        documents = (
            self.document_repository.list_by_status(
                status=query.status,
            )
        )

        return [
            self._to_dto(document)
            for document in documents
        ]

    def list_all(self) -> list[DocumentDto]:
        # list_by_status is the only unfiltered listing exposed by the
        # repository contract; "archived" is the least surprising filter
        # to drop so admins still see every active document.
        documents = (
            self.document_repository.list_by_status(
                status="pending",
            )
        )

        for status_value in ("processing", "ready", "failed"):
            documents.extend(
                self.document_repository.list_by_status(
                    status=status_value,
                )
            )

        return [
            self._to_dto(document)
            for document in documents
        ]

    def update(
        self,
        command: UpdateDocumentCommand,
    ) -> DocumentDto:
        document = self.document_repository.get_by_id(
            command.document_id,
        )

        if document is None:
            raise ApplicationError(
                message="Document not found.",
                code="document_not_found",
                status_code=404,
            )

        updated = self.document_repository.update(
            document_id=document.id,
            title=DocumentTitle(
                command.title,
            ).value,
            description=command.description,
            status=command.status,
            failure_reason=None,
        )

        return self._to_dto(updated)

    def mark_processing(
        self,
        command: MarkDocumentProcessingCommand,
    ) -> DocumentDto:
        return self._change_status(
            document_id=command.document_id,
            status="processing",
            failure_reason=None,
        )

    def mark_ready(
        self,
        command: MarkDocumentReadyCommand,
    ) -> DocumentDto:
        return self._change_status(
            document_id=command.document_id,
            status="ready",
            failure_reason=None,
        )

    def mark_failed(
        self,
        command: MarkDocumentFailedCommand,
    ) -> DocumentDto:
        return self._change_status(
            document_id=command.document_id,
            status="failed",
            failure_reason=command.failure_reason,
        )

    def archive(
        self,
        command: ArchiveDocumentCommand,
    ) -> DocumentDto:
        return self._change_status(
            document_id=command.document_id,
            status="archived",
            failure_reason=None,
        )

    def delete(
        self,
        command: DeleteDocumentCommand,
        vector_store: object | None = None,
    ) -> bool:
        """Permanently remove a document and un-index its vectors.

        Vector cleanup is best-effort: the DB row is removed even if the
        vector store reports an error, so the admin is never stuck with
        an undeletable entry.
        """
        document = self.document_repository.get_by_id(
            command.document_id,
        )

        if document is None:
            raise ApplicationError(
                message="Document not found.",
                code="document_not_found",
                status_code=404,
            )

        if vector_store is not None and hasattr(
            vector_store,
            "delete_document_chunks",
        ):
            try:
                vector_store.delete_document_chunks(
                    document_id=str(document.id),
                )
            except Exception:
                # Swallow and continue; storage/vector drift is less
                # harmful than blocking the delete entirely.
                pass

        return self.document_repository.delete(
            str(document.id),
        )


    def _change_status(
        self,
        *,
        document_id: UUID,
        status: str,
        failure_reason: str | None,
    ) -> DocumentDto:
        document = self.document_repository.get_by_id(
            document_id,
        )

        if document is None:
            raise ApplicationError(
                message="Document not found.",
                code="document_not_found",
                status_code=404,
            )

        allowed=self._ALLOWED_TRANSITIONS.get(document.status, set())

        if status not in allowed:
            raise ApplicationError(
            message=(
                f"Cannot change document status from "
                f"'{document.status}' to '{status}'."
            ),
            code="document_invalid_status_transition",
            status_code=409,
        )

        updated = self.document_repository.update(
            document_id=document.id,
            title=document.title,
            description=document.description,
            status=status,
            failure_reason=failure_reason,
        )

        return self._to_dto(updated)

    def _upload_to_storage(
        self,
        *,
        path: str,
        content: bytes,
        content_type: str | None,
    ) -> str:
        provider = self.storage_provider

        if hasattr(provider, "upload"):
            result = provider.upload(
                path=path,
                content=content,
                content_type=content_type,
            )
        elif hasattr(provider, "upload_bytes"):
            result = provider.upload_bytes(
                path=path,
                content=content,
                content_type=content_type,
            )
        else:
            raise ApplicationError(
                message=(
                    "Storage provider does not expose "
                    "upload() or upload_bytes()."
                ),
                code="invalid_storage_provider",
                status_code=500,
            )

        if isinstance(result, str):
            return result

        return path

    @staticmethod
    def _to_dto(
        document: Document,
    ) -> DocumentDto:
        return DocumentDto(
            id=document.id,
            application_id=document.application_id,
            knowledge_base_id=document.knowledge_base_id,
            title=document.title,
            description=document.description,
            source_type=document.source_type,
            source_uri=document.source_uri,
            storage_path=document.storage_path,
            mime_type=document.mime_type,
            file_size_bytes=document.file_size_bytes,
            checksum_sha256=document.checksum_sha256,
            status=document.status,
            failure_reason=document.failure_reason,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )