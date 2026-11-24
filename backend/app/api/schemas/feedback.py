from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class FeedbackRatingDistributionResponse(BaseModel):
    rating: int
    count: int


class FeedbackAnalyticsResponse(BaseModel):
    response_count: int
    average_rating: float
    five_star_responses: int
    positive_rating_percentage: float
    distribution: list[FeedbackRatingDistributionResponse]


class ApplicationFeedbackResponse(BaseModel):
    id: UUID
    application_id: UUID
    conversation_id: UUID
    conversation_title: str | None
    rating: int
    created_at: datetime
    feedback_text: str | None = None
