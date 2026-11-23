from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models.conversation_model import ConversationModel
from app.infrastructure.db.models.lead_model import (
    ConversationFeedbackModel,
    LeadModel,
)
from app.modules.leads.domain.entities import ConversationFeedback, Lead
from app.modules.leads.domain.repository_interfaces import LeadRepositoryInterface
from app.modules.leads.infrastructure.mappers import (
    map_feedback_model,
    map_lead_model,
)


class SqlAlchemyLeadRepository(LeadRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self._session = session

    def conversation_belongs_to_application(
        self,
        *,
        conversation_id: str,
        application_id: str,
    ) -> bool:
        statement = select(ConversationModel.id).where(
            ConversationModel.id == UUID(conversation_id),
            ConversationModel.application_id == UUID(application_id),
        )
        return self._session.execute(statement).scalar_one_or_none() is not None

    def get_by_idempotency_key(
        self,
        *,
        application_id: str,
        idempotency_key: str,
    ) -> Lead | None:
        model = self._session.execute(
            select(LeadModel).where(
                LeadModel.application_id == UUID(application_id),
                LeadModel.idempotency_key == idempotency_key,
            )
        ).scalar_one_or_none()
        return None if model is None else map_lead_model(model)

    def create(self, **values) -> Lead:
        model = LeadModel(**values)
        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError:
            existing = self.get_by_idempotency_key(
                application_id=str(values["application_id"]),
                idempotency_key=values["idempotency_key"],
            )
            if existing is None:
                raise
            return existing
        self._session.refresh(model)
        return map_lead_model(model)

    def get_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
    ) -> Lead | None:
        model = self._session.execute(
            select(LeadModel).where(
                LeadModel.application_id == UUID(application_id),
                LeadModel.id == UUID(lead_id),
            )
        ).scalar_one_or_none()
        return None if model is None else map_lead_model(model)

    def list_for_application(
        self,
        *,
        application_id: str,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        limit: int,
        offset: int,
    ) -> list[Lead]:
        statement = self._filtered_statement(
            application_id=application_id,
            status=status,
            created_from=created_from,
            created_to=created_to,
        ).order_by(LeadModel.created_at.desc(), LeadModel.id.desc())
        models = (
            self._session.execute(statement.limit(limit).offset(offset)).scalars().all()
        )
        return [map_lead_model(model) for model in models]

    def update_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
        status: str,
        internal_note: str | None,
    ) -> Lead | None:
        model = self._session.execute(
            select(LeadModel).where(
                LeadModel.application_id == UUID(application_id),
                LeadModel.id == UUID(lead_id),
            )
        ).scalar_one_or_none()
        if model is None:
            return None
        model.status = status
        model.internal_note = internal_note
        self._session.flush()
        self._session.refresh(model)
        return map_lead_model(model)

    def delete_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
    ) -> bool:
        result = self._session.execute(
            delete(LeadModel).where(
                LeadModel.application_id == UUID(application_id),
                LeadModel.id == UUID(lead_id),
            )
        )
        return result.rowcount == 1

    def list_for_export(
        self,
        *,
        application_id: str,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> list[Lead]:
        models = (
            self._session.execute(
                self._filtered_statement(
                    application_id=application_id,
                    status=status,
                    created_from=created_from,
                    created_to=created_to,
                ).order_by(LeadModel.created_at.desc(), LeadModel.id.desc())
            )
            .scalars()
            .all()
        )
        return [map_lead_model(model) for model in models]

    def has_lead_for_conversation(
        self,
        *,
        application_id: str,
        conversation_id: str,
    ) -> bool:
        statement = (
            select(LeadModel.id)
            .where(
                LeadModel.application_id == UUID(application_id),
                LeadModel.conversation_id == UUID(conversation_id),
            )
            .limit(1)
        )
        return self._session.execute(statement).scalar_one_or_none() is not None

    def get_feedback(
        self,
        *,
        conversation_id: str,
    ) -> ConversationFeedback | None:
        model = self._session.execute(
            select(ConversationFeedbackModel).where(
                ConversationFeedbackModel.conversation_id == UUID(conversation_id)
            )
        ).scalar_one_or_none()
        return None if model is None else map_feedback_model(model)

    def save_feedback(
        self,
        *,
        application_id: str,
        conversation_id: str,
        rating: int,
    ) -> ConversationFeedback:
        existing = self.get_feedback(conversation_id=conversation_id)
        if existing is not None:
            return existing

        model = ConversationFeedbackModel(
            application_id=UUID(application_id),
            conversation_id=UUID(conversation_id),
            rating=rating,
        )
        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError:
            existing = self.get_feedback(conversation_id=conversation_id)
            if existing is None:
                raise
            return existing
        self._session.refresh(model)
        return map_feedback_model(model)

    @staticmethod
    def _filtered_statement(
        *,
        application_id: str,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ):
        statement = select(LeadModel).where(
            LeadModel.application_id == UUID(application_id)
        )
        if status:
            statement = statement.where(LeadModel.status == status)
        if created_from:
            statement = statement.where(LeadModel.created_at >= created_from)
        if created_to:
            statement = statement.where(LeadModel.created_at < created_to)
        return statement
