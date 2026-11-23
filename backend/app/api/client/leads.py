from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.client.dependencies import (
    get_client_application_context,
    get_widget_application_id,
)
from app.api.dependencies import get_session
from app.api.schemas.leads import (
    ConversationFeedbackRequest,
    ConversationFeedbackResponse,
    LeadSubmissionRequest,
    LeadSubmissionResponse,
)
from app.modules.leads.application.services import LeadManagementService
from app.modules.leads.infrastructure.repositories import SqlAlchemyLeadRepository
from app.modules.security.domain.entities import ClientApplicationContext

router = APIRouter(prefix="/client", tags=["Client Lead Capture"])


def _service(session: Session) -> LeadManagementService:
    return LeadManagementService(SqlAlchemyLeadRepository(session))


def _submit_lead(
    payload: LeadSubmissionRequest,
    *,
    application_id: str,
    session: Session,
) -> LeadSubmissionResponse:
    lead = _service(session).submit(
        application_id=application_id,
        conversation_id=str(payload.conversation_id),
        idempotency_key=str(payload.idempotency_key),
        name=payload.name,
        email=payload.email,
        phone=payload.phone,
        message=payload.message,
        consent=payload.consent,
        consent_text_version=payload.consent_text_version,
    )
    return LeadSubmissionResponse(
        id=lead.id,
        status=lead.status,
        created_at=lead.created_at,
    )


def _submit_feedback(
    conversation_id: str,
    payload: ConversationFeedbackRequest,
    *,
    application_id: str,
    session: Session,
) -> ConversationFeedbackResponse:
    feedback = _service(session).submit_feedback(
        application_id=application_id,
        conversation_id=conversation_id,
        rating=payload.rating,
    )
    return ConversationFeedbackResponse(
        id=feedback.id,
        conversation_id=feedback.conversation_id,
        rating=feedback.rating,
        created_at=feedback.created_at,
    )


@router.post(
    "/leads",
    response_model=LeadSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_client_lead(
    payload: LeadSubmissionRequest,
    application_context: ClientApplicationContext = Depends(
        get_client_application_context
    ),
    session: Session = Depends(get_session),
) -> LeadSubmissionResponse:
    return _submit_lead(
        payload,
        application_id=str(application_context.application_id),
        session=session,
    )


@router.post(
    "/widget/leads",
    response_model=LeadSubmissionResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_widget_lead(
    payload: LeadSubmissionRequest,
    application_id: str = Depends(get_widget_application_id),
    session: Session = Depends(get_session),
) -> LeadSubmissionResponse:
    return _submit_lead(payload, application_id=application_id, session=session)


@router.post(
    "/conversations/{conversation_id}/feedback",
    response_model=ConversationFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_client_feedback(
    conversation_id: str,
    payload: ConversationFeedbackRequest,
    application_context: ClientApplicationContext = Depends(
        get_client_application_context
    ),
    session: Session = Depends(get_session),
) -> ConversationFeedbackResponse:
    return _submit_feedback(
        conversation_id,
        payload,
        application_id=str(application_context.application_id),
        session=session,
    )


@router.post(
    "/widget/conversations/{conversation_id}/feedback",
    response_model=ConversationFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_widget_feedback(
    conversation_id: str,
    payload: ConversationFeedbackRequest,
    application_id: str = Depends(get_widget_application_id),
    session: Session = Depends(get_session),
) -> ConversationFeedbackResponse:
    return _submit_feedback(
        conversation_id,
        payload,
        application_id=application_id,
        session=session,
    )
