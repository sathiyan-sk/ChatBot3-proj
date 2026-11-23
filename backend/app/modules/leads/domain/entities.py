from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class Lead:
    id: str
    application_id: str
    conversation_id: str | None
    idempotency_key: str
    name: str
    email: str | None
    phone: str | None
    message: str | None
    status: str
    internal_note: str | None
    consent_given: bool
    consent_text_version: str
    consent_text: str
    consented_at: datetime
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class ConversationFeedback:
    id: str
    application_id: str
    conversation_id: str
    rating: int
    created_at: datetime
    updated_at: datetime
