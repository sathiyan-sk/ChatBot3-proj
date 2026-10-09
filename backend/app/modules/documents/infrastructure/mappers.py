from __future__ import annotations

from app.infrastructure.db.models.document_model import DocumentModel
from app.modules.documents.domain.entities import Document


def map_document_model_to_entity(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        application_id=model.application_id,
        knowledge_base_id=model.knowledge_base_id,
        title=model.title,
        description=model.description,
        source_type=model.source_type,
        source_uri=model.source_uri,
        storage_path=model.storage_path,
        mime_type=model.mime_type,
        file_size_bytes=model.file_size_bytes,
        checksum_sha256=model.checksum_sha256,
        status=model.status,
        failure_reason=model.failure_reason,
        ingestion_version=model.ingestion_version,
        ready_version=model.ready_version,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )