from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.modules.leads.domain.entities import (
    ConversationFeedback,
    ConversationFeedbackEntry,
    FeedbackAnalytics,
    Lead,
    LeadOperationalOverview,
)


class LeadRepositoryInterface(ABC):
    @abstractmethod
    def conversation_belongs_to_application(
        self,
        *,
        conversation_id: str,
        application_id: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_by_idempotency_key(
        self,
        *,
        application_id: str,
        idempotency_key: str,
    ) -> Lead | None:
        raise NotImplementedError

    @abstractmethod
    def create(self, **values) -> Lead:
        raise NotImplementedError

    @abstractmethod
    def get_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
    ) -> Lead | None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def operational_overview_for_application(
        self,
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> LeadOperationalOverview:
        raise NotImplementedError

    @abstractmethod
    def update_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
        status: str,
        internal_note: str | None,
    ) -> Lead | None:
        raise NotImplementedError

    @abstractmethod
    def delete_for_application(
        self,
        *,
        application_id: str,
        lead_id: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def list_for_export(
        self,
        *,
        application_id: str,
        status: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
    ) -> list[Lead]:
        raise NotImplementedError

    @abstractmethod
    def has_lead_for_conversation(
        self,
        *,
        application_id: str,
        conversation_id: str,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def get_feedback(
        self,
        *,
        conversation_id: str,
    ) -> ConversationFeedback | None:
        raise NotImplementedError

    @abstractmethod
    def save_feedback(
        self,
        *,
        application_id: str,
        conversation_id: str,
        rating: int,
    ) -> ConversationFeedback:
        raise NotImplementedError

    @abstractmethod
    def feedback_analytics_for_application(
        self,
        *,
        application_id: str,
        created_from: datetime | None,
        created_to: datetime | None,
        rating: int | None,
    ) -> FeedbackAnalytics:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError
