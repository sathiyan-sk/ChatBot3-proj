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
    first_contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class LeadOperationalOverview:
    total_count: int
    new_count: int
    contacted_count: int
    closed_count: int
    average_first_contact_hours: float | None
    measured_first_contact_count: int


@dataclass(slots=True, frozen=True)
class ConversationFeedback:
    id: str
    application_id: str
    conversation_id: str
    rating: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True, frozen=True)
class ConversationFeedbackEntry:
    feedback: ConversationFeedback
    conversation_title: str | None


@dataclass(slots=True, frozen=True)
class FeedbackRatingCount:
    rating: int
    count: int


@dataclass(slots=True, frozen=True)
class FeedbackAnalytics:
    response_count: int
    average_rating: float
    five_star_responses: int
    positive_rating_percentage: float
    distribution: tuple[FeedbackRatingCount, ...]
