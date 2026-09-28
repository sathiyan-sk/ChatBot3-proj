from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    conversation_id: str | None = Field(
        default=None,
    )
    conversation_identity: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=8000,
    )
    conversation_title: str | None = Field(
        default=None,
        max_length=255,
    )


class CitationResponse(BaseModel):
    document_id: str
    title: str
    chunk_id: str
    source_uri: str | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    answer: str
    citations: list[CitationResponse] = Field(
        default_factory=list,
    )
    created_at: datetime