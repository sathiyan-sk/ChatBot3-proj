from __future__ import annotations

import os

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models.api_key_model import ApiKeyModel
from app.infrastructure.db.models.application_model import ApplicationModel
from app.infrastructure.db.models.knowledge_base_model import KnowledgeBaseModel
from app.infrastructure.db.models.settings_model import SettingsModel
from app.modules.applications.domain.entities import Application
from app.modules.applications.domain.repository_interfaces import (
    ApplicationProvisioningRepository,
    ApplicationRepository,
)
from app.modules.applications.infrastructure.mappers import map_application_model_to_entity
from app.modules.applications.domain.policies import build_application_slug


def _normalize_allowed_origins(allowed_origins: list[str] | None) -> list[str]:
    if not allowed_origins:
        return []
    return [origin.strip() for origin in allowed_origins if origin and origin.strip()]


class ApplicationSqlAlchemyRepository(ApplicationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        name: str,
        slug: str,
        description: str | None,
        client_type: str,
        allowed_origins: list[str] | None,
    ) -> Application:
        model = ApplicationModel(
            name=name,
            slug=slug,
            description=description,
            client_type=client_type,
            allowed_origins=_normalize_allowed_origins(allowed_origins),
            is_active=True,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return map_application_model_to_entity(model)

    def get_by_id(self, application_id: str) -> Application | None:
        model = self.get_model_by_id(application_id)
        if model is None:
            return None
        return map_application_model_to_entity(model)

    def get_model_by_id(self, application_id: str) -> ApplicationModel | None:
        normalized_application_id = str(application_id)
        statement = select(ApplicationModel).where(ApplicationModel.id == normalized_application_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Application | None:
        statement = select(ApplicationModel).where(ApplicationModel.slug == slug)
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            return None
        return map_application_model_to_entity(model)

    def list_all(self) -> list[Application]:
        statement = select(ApplicationModel).order_by(ApplicationModel.created_at.desc())
        models = self._session.execute(statement).scalars().all()
        return [map_application_model_to_entity(item) for item in models]

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
        model = self.get_model_by_id(application_id)
        if model is None:
            raise ValueError(f"Application '{application_id}' does not exist.")

        model.name = name
        model.slug = slug
        model.description = description
        model.client_type = client_type
        model.allowed_origins = _normalize_allowed_origins(allowed_origins)
        model.is_active = is_active

        self._session.flush()
        self._session.refresh(model)

        return map_application_model_to_entity(model)


class ApplicationProvisioningSqlAlchemyRepository(ApplicationProvisioningRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_default_knowledge_base(
        self,
        *,
        application_id: str,
        application_name: str,
    ) -> None:
        base_slug = build_application_slug(application_name)
        slug = f"{base_slug}-kb-{application_id[:8]}"

        model = KnowledgeBaseModel(
            application_id=application_id,
            name=f"{application_name} Knowledge Base",
            slug=slug,
            status="ready",
            is_active=True,
        )
        self._session.add(model)
        self._session.flush()

    def create_default_settings(self, *, application_id: str) -> None:
        default_retention_days = max(
            1,
            int(os.getenv("CHAT_HISTORY_RETENTION_DAYS", "30")),
        )
        model = SettingsModel(
            application_id=application_id,
            llm_temperature="0.2",
            max_context_messages=12,
            inactivity_timeout_minutes=30,
            retention_days=default_retention_days,
            prompt_system_template=None,
        )
        self._session.add(model)
        self._session.flush()

    def create_api_key(
        self,
        *,
        application_id: str,
        key_name: str,
        key_prefix: str,
        key_hash: str,
    ) -> None:
        model = ApiKeyModel(
            application_id=application_id,
            name=key_name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            is_active=True,
        )
        self._session.add(model)
        self._session.flush()

    def get_model_by_id(self, application_id: str) -> ApplicationModel | None:
        normalized_application_id = str(application_id)
        statement = select(ApplicationModel).where(ApplicationModel.id == normalized_application_id)
        return self._session.execute(statement).scalar_one_or_none()

    def get_by_slug(self, slug: str) -> Application | None:
        statement = select(ApplicationModel).where(ApplicationModel.slug == slug)
        model = self._session.execute(statement).scalar_one_or_none()
        if model is None:
            return None
        return map_application_model_to_entity(model)

    def list_all(self) -> list[Application]:
        statement = select(ApplicationModel).order_by(ApplicationModel.created_at.desc())
        models = self._session.execute(statement).scalars().all()
        return [map_application_model_to_entity(item) for item in models]