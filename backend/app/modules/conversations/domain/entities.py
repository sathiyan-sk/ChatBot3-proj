from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class Conversation:
    id: str
    application_id: str
    conversation_identity: str
    title: str | None
    summary: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    sequence_number: int
    citation_payload: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class ConversationListItem:
    conversation: Conversation
    message_count: int
    last_activity_at: datetime


@dataclass(slots=True, frozen=True)
class ConversationListPage:
    items: list[ConversationListItem]
    total: int