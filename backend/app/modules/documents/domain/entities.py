from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

@dataclass(slots=True, frozen=True)
class Document:
    id: UUID
    application_id: UUID
    knowledge_base_id: UUID
    title: str
    description: str | None
    source_type: str
    source_uri: str | None
    storage_path: str | None
    mime_type: str | None
    file_size_bytes: int | None
    checksum_sha256: str | None
    status: str
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime
    ingestion_version: int = 0
    ready_version: int | None = None