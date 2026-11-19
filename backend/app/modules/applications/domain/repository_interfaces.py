from __future__ import annotations

from abc import ABC, abstractmethod

from app.modules.applications.domain.entities import Application


class ApplicationRepository(ABC):
    @abstractmethod
    def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        client_type: str,
        allowed_origins: list[str] | None,
    ) -> Application:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, application_id: str) -> Application | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_slug(self, slug: str) -> Application | None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Application]:
        raise NotImplementedError

    @abstractmethod
    def update(
        self,
        *,
        application_id: str,
        name: str,
        slug: str,
        description: str | None,
        client_type: str,
        allowed_origins: list[str] | None,
        is_active: bool,
    ) -> Application:
        raise NotImplementedError


class ApplicationProvisioningRepository(ABC):
    @abstractmethod
    def create_default_knowledge_base(self, *, application_id: str, application_name: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_default_settings(
        self,
        *,
        application_id: str,
        parser_provider: str,
        embedding_provider: str,
        embedding_model: str,
        llm_provider: str,
        llm_model: str,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def create_api_key(
        self,
        *,
        application_id: str,
        key_name: str,
        key_prefix: str,
        key_hash: str,
    ) -> None:
        raise NotImplementedError