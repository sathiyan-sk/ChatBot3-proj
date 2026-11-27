from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateApplicationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    client_type: str = Field(..., min_length=1, max_length=50)
    allowed_origins: list[str] = Field(default_factory=list)


class UpdateApplicationRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=2000)
    client_type: str = Field(..., min_length=1, max_length=50)
    allowed_origins: list[str] = Field(default_factory=list)
    is_active: bool = True


class ApplicationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    client_type: str
    allowed_origins: list[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CreatedApplicationResponse(BaseModel):
    application: ApplicationResponse
    api_key: str
    api_key_prefix: str


class ApplicationDeletionSummaryResponse(BaseModel):
    knowledge_bases: int
    documents: int
    processing_documents: int
    stored_files: int
    indexed_chunks: int
    conversations: int
    messages: int
    leads: int
    feedback: int
    api_keys: int
    widgets: int
    settings: int
    upload_intents: int
    recent_uploads: int