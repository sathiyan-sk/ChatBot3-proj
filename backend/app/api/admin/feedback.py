from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_session
from app.api.schemas.feedback import (
    ApplicationFeedbackResponse,
    FeedbackAnalyticsResponse,
    FeedbackRatingDistributionResponse,
)
from app.modules.leads.application.services import LeadManagementService
from app.modules.leads.infrastructure.repositories import SqlAlchemyLeadRepository

router = APIRouter(prefix="/admin/feedback", tags=["Admin Feedback"])


def _service(session: Session) -> LeadManagementService:
    return LeadManagementService(SqlAlchemyLeadRepository(session))


@router.get(
    "/application/{application_id}/analytics",
    response_model=FeedbackAnalyticsResponse,
)
def get_application_feedback_analytics(
    application_id: str,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    rating: int | None = Query(default=None, ge=1, le=5),
    session: Session = Depends(get_session),
) -> FeedbackAnalyticsResponse:
    analytics = _service(session).feedback_analytics(
        application_id=application_id,
        created_from=created_from,
        created_to=created_to,
        rating=rating,
    )
    return FeedbackAnalyticsResponse(
        response_count=analytics.response_count,
        average_rating=analytics.average_rating,
        five_star_responses=analytics.five_star_responses,
        positive_rating_percentage=analytics.positive_rating_percentage,
        distribution=[
            FeedbackRatingDistributionResponse(rating=item.rating, count=item.count)
            for item in analytics.distribution
        ],
    )


@router.get(
    "/application/{application_id}",
    response_model=list[ApplicationFeedbackResponse],
)
def list_application_feedback(
    application_id: str,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    rating: int | None = Query(default=None, ge=1, le=5),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
) -> list[ApplicationFeedbackResponse]:
    entries = _service(session).list_feedback(
        application_id=application_id,
        limit=limit,
        offset=offset,
        created_from=created_from,
        created_to=created_to,
        rating=rating,
    )
    return [
        ApplicationFeedbackResponse(
            id=entry.feedback.id,
            application_id=entry.feedback.application_id,
            conversation_id=entry.feedback.conversation_id,
            conversation_title=entry.conversation_title,
            rating=entry.feedback.rating,
            created_at=entry.feedback.created_at,
        )
        for entry in entries
    ]
