from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

LeadStatus = Literal["new", "contacted", "closed"]


class LeadSubmissionRequest(BaseModel):
    conversation_id: UUID
    idempotency_key: UUID
    name: str = Field(min_length=1, max_length=120)
    email: str | None = Field(default=None, max_length=254)
    phone: str | None = Field(default=None, max_length=32)
    message: str | None = Field(default=None, max_length=2000)
    consent: bool
    consent_text_version: str = Field(min_length=1, max_length=32)


class LeadSubmissionResponse(BaseModel):
    id: UUID
    status: LeadStatus
    created_at: datetime


class ConversationFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)


class ConversationFeedbackResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    rating: int
    created_at: datetime


class LeadResponse(BaseModel):
    id: UUID
    application_id: UUID
    conversation_id: UUID | None
    name: str
    email: str | None
    phone: str | None
    message: str | None
    status: LeadStatus
    internal_note: str | None
    consent_given: bool
    consent_text_version: str
    consent_text: str
    consented_at: datetime
    first_contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LeadOperationalOverviewResponse(BaseModel):
    total_count: int
    new_count: int
    contacted_count: int
    closed_count: int
    average_first_contact_hours: float | None
    measured_first_contact_count: int


class LeadUpdateRequest(BaseModel):
    status: LeadStatus
    internal_note: str | None = Field(default=None, max_length=5000)
