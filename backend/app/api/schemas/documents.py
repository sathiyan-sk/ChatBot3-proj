from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class CreateDocumentRequest(BaseModel):
    knowledge_base_id: UUID
    title: str = Field(
        min_length=1,
    )
    description: str | None = None
    source_type: str = "file"
    source_uri: str | None = None
    refresh_interval_hours: int | None = Field(default=None, ge=1, le=720)


class UpdateWebsiteRefreshScheduleRequest(BaseModel):
    refresh_interval_hours: int | None = Field(default=None, ge=1, le=720)


class UpdateDocumentRequest(BaseModel):
    title: str = Field(
        min_length=1,
    )
    description: str | None = None
    status: str


class MarkDocumentFailedRequest(BaseModel):
    failure_reason: str = Field(
        min_length=1,
    )


class DocumentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: UUID
    application_id: UUID
    knowledge_base_id: UUID
    title: str
    description: str | None = None
    source_type: str
    source_uri: str | None = None
    storage_path: str | None = None
    mime_type: str | None = None
    file_size_bytes: int | None = None
    checksum_sha256: str | None = None
    status: str
    failure_reason: str | None = None
    failure_code: str | None = None
    ingestion_version: int = 0
    ready_version: int | None = None
    ingestion_attempt_count: int = 0
    refresh_interval_hours: int | None = None
    next_refresh_at: datetime | None = None
    created_at: datetime
    updated_at: datetime