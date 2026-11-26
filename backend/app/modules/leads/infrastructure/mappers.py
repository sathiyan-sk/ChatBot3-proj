from __future__ import annotations

from app.infrastructure.db.models.lead_model import (
    ConversationFeedbackModel,
    LeadModel,
)
from app.modules.leads.domain.entities import ConversationFeedback, Lead


def map_lead_model(model: LeadModel) -> Lead:
    return Lead(
        id=str(model.id),
        application_id=str(model.application_id),
        conversation_id=(
            str(model.conversation_id) if model.conversation_id is not None else None
        ),
        idempotency_key=model.idempotency_key,
        name=model.name,
        email=model.email,
        phone=model.phone,
        message=model.message,
        status=model.status,
        internal_note=model.internal_note,
        consent_given=model.consent_given,
        consent_text_version=model.consent_text_version,
        consent_text=model.consent_text,
        consented_at=model.consented_at,
        first_contacted_at=model.first_contacted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def map_feedback_model(model: ConversationFeedbackModel) -> ConversationFeedback:
    return ConversationFeedback(
        id=str(model.id),
        application_id=str(model.application_id),
        conversation_id=str(model.conversation_id),
        rating=model.rating,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
