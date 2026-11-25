from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatHistoryMessageRequest(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=8000)


class ChatMessageRequest(BaseModel):
    top_k: int = Field(default=5, ge=1, le=20)
    application_id: str | None = Field(default=None, min_length=1, max_length=36)
    conversation_messages: list[ChatHistoryMessageRequest] = Field(
        default_factory=list,
        max_length=40,
    )
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


class ChatActionResponse(BaseModel):
    type: str
    label: str
    consent_text: str
    consent_text_version: str


class ChatMessageResponse(BaseModel):
    conversation_id: str
    application_id: str | None = None
    answer: str
    citations: list[CitationResponse] = Field(
        default_factory=list,
    )
    actions: list[ChatActionResponse] = Field(default_factory=list)
    created_at: datetime
