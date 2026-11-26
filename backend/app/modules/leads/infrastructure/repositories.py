from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import case, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.infrastructure.db.models.conversation_model import ConversationModel
from app.infrastructure.db.models.lead_model import (
    ConversationFeedbackModel,
    LeadModel,
)
from app.modules.leads.domain.entities import (
    ConversationFeedback,
    ConversationFeedbackEntry,
    FeedbackAnalytics,
    FeedbackRatingCount,
    Lead,
    LeadOperationalOverview,
)
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

    def operational_overview_for_application(
        self,
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> LeadOperationalOverview:
        first_contact_seconds = func.extract(
            "epoch",
            LeadModel.first_contacted_at - LeadModel.created_at,
        )
        totals = self._session.execute(
            select(
                func.count(LeadModel.id),
                func.coalesce(
                    func.sum(case((LeadModel.status == "new", 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((LeadModel.status == "contacted", 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((LeadModel.status == "closed", 1), else_=0)),
                    0,
                ),
                func.avg(first_contact_seconds),
                func.count(LeadModel.first_contacted_at),
            )
            .where(
                *self._lead_date_filters(
                    application_id=application_id,
                    created_from=created_from,
                    created_to=created_to,
                )
            )
        ).one()
        average_seconds = totals[4]
        return LeadOperationalOverview(
            total_count=int(totals[0]),
            new_count=int(totals[1]),
            contacted_count=int(totals[2]),
            closed_count=int(totals[3]),
            average_first_contact_hours=(
                float(average_seconds) / 3600 if average_seconds is not None else None
            ),
            measured_first_contact_count=int(totals[5]),
        )

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
        if (
            status == "contacted"
            and model.status != "contacted"
            and model.first_contacted_at is None
        ):
            model.first_contacted_at = func.coalesce(
                LeadModel.first_contacted_at,
                func.now(),
            )
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

    def feedback_analytics_for_application(
        self,
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
        rating: int | None,
    ) -> FeedbackAnalytics:
        filters = self._feedback_filters(
            application_id=application_id,
            created_from=created_from,
            created_to=created_to,
            rating=rating,
        )
        totals = self._session.execute(
            select(
                func.count(ConversationFeedbackModel.id),
                func.coalesce(func.avg(ConversationFeedbackModel.rating), 0.0),
                func.coalesce(
                    func.sum(case((ConversationFeedbackModel.rating == 5, 1), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((ConversationFeedbackModel.rating >= 4, 1), else_=0)),
                    0,
                ),
            )
            .select_from(ConversationFeedbackModel)
            .join(
                ConversationModel,
                ConversationModel.id == ConversationFeedbackModel.conversation_id,
            )
            .where(*filters)
        ).one()
        response_count = int(totals[0])
        positive_count = int(totals[3])
        distribution_rows = self._session.execute(
            select(
                ConversationFeedbackModel.rating,
                func.count(ConversationFeedbackModel.id),
            )
            .select_from(ConversationFeedbackModel)
            .join(
                ConversationModel,
                ConversationModel.id == ConversationFeedbackModel.conversation_id,
            )
            .where(*filters)
            .group_by(ConversationFeedbackModel.rating)
        ).all()
        counts = {int(row[0]): int(row[1]) for row in distribution_rows}
        return FeedbackAnalytics(
            response_count=response_count,
            average_rating=float(totals[1]),
            five_star_responses=int(totals[2]),
            positive_rating_percentage=(
                positive_count * 100.0 / response_count if response_count else 0.0
            ),
            distribution=tuple(
                FeedbackRatingCount(rating=star, count=counts.get(star, 0))
                for star in range(1, 6)
            ),
        )

    def list_feedback_for_application(
        self,
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
        rating: int | None,
        limit: int,
        offset: int,
    ) -> list[ConversationFeedbackEntry]:
        rows = self._session.execute(
            select(ConversationFeedbackModel, ConversationModel.title)
            .select_from(ConversationFeedbackModel)
            .join(
                ConversationModel,
                ConversationModel.id == ConversationFeedbackModel.conversation_id,
            )
            .where(
                *self._feedback_filters(
                    application_id=application_id,
                    created_from=created_from,
                    created_to=created_to,
                    rating=rating,
                )
            )
            .order_by(
                ConversationFeedbackModel.created_at.desc(),
                ConversationFeedbackModel.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).all()
        return [
            ConversationFeedbackEntry(
                feedback=map_feedback_model(model),
                conversation_title=title,
            )
            for model, title in rows
        ]

    @staticmethod
    def _feedback_filters(
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
        rating: int | None,
    ) -> list[ColumnElement[bool]]:
        filters = [
            ConversationFeedbackModel.application_id == UUID(application_id),
            ConversationModel.application_id == UUID(application_id),
        ]
        if created_from:
            filters.append(ConversationFeedbackModel.created_at >= created_from)
        if created_to:
            filters.append(ConversationFeedbackModel.created_at < created_to)
        if rating is not None:
            filters.append(ConversationFeedbackModel.rating == rating)
        return filters

    @staticmethod
    def _filtered_statement(
        *,
        application_id: str,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ):
        statement = select(LeadModel).where(
            *SqlAlchemyLeadRepository._lead_date_filters(
                application_id=application_id,
                created_from=created_from,
                created_to=created_to,
            )
        )
        if status:
            statement = statement.where(LeadModel.status == status)
        return statement

    @staticmethod
    def _lead_date_filters(
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> list[ColumnElement[bool]]:
        filters = [LeadModel.application_id == UUID(application_id)]
        if created_from:
            filters.append(LeadModel.created_at >= created_from)
        if created_to:
            filters.append(LeadModel.created_at < created_to)
        return filters
