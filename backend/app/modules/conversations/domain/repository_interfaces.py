from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.conversations.domain.entities import Conversation, Message


class ConversationRepositoryInterface(ABC):
    @abstractmethod
    def create(
        self,
        *,
        application_id: str,
        conversation_identity: str,
        title: str | None,
        summary: str | None,
        is_active: bool,
    ) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, conversation_id: str) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def get_active_by_identity(
        self,
        *,
        application_id: str,
        conversation_identity: str,
    ) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id_and_application_id(
    self,
    *,
    conversation_id: str,
    application_id: str,
    ) -> Conversation | None:
        raise NotImplementedError

    @abstractmethod
    def list_by_application_id(self, application_id: str) -> list[Conversation]:
        raise NotImplementedError

    @abstractmethod
    def list_by_identity(
        self,
        *,
        application_id: str,
        conversation_identity: str,
    ) -> list[Conversation]:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        *,
        conversation_id: str,
        title: str | None,
        summary: str | None,
        is_active: bool,
    ) -> Conversation:
        raise NotImplementedError

    @abstractmethod
    def touch_activity(self, conversation_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete_expired_conversations(
        self,
        *,
        default_retention_days: int,
        application_id: str | None = None,
    ) -> int:
        raise NotImplementedError


class MessageRepositoryInterface(ABC):
    @abstractmethod
    def create(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        sequence_number: int,
        citation_payload: str | None,
    ) -> Message:
        raise NotImplementedError

    @abstractmethod
    def list_by_conversation_id(self, conversation_id: str) -> list[Message]:
        raise NotImplementedError

    @abstractmethod
    def get_latest_sequence_number(self, conversation_id: str) -> int:
        raise NotImplementedError