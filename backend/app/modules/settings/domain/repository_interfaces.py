from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.settings.domain.entities import PlatformSettings


class SettingsRepositoryInterface(ABC):
    @abstractmethod
    def create(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
        parser_provider: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> PlatformSettings:
        raise NotImplementedError

    @abstractmethod
    def get_by_application_id(self, application_id: str) -> PlatformSettings | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_application_id_for_update(
        self,
        application_id: str,
    ) -> PlatformSettings | None:
        raise NotImplementedError

    @abstractmethod
    def has_published_vectors(self, application_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
        parser_provider: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> PlatformSettings:
        raise NotImplementedError