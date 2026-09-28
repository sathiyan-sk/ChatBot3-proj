from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class ResolveConversationCommand:
    application_id: str
    conversation_identity: str
    title: str | None = None
    inactivity_timeout_minutes: int | None = None


@dataclass(slots=True, frozen=True)
class AppendMessageCommand:
    conversation_id: str
    role: str
    content: str
    citation_payload: str | None = None


@dataclass(slots=True, frozen=True)
class UpdateConversationCommand:
    conversation_id: str
    title: str | None
    summary: str | None
    is_active: bool