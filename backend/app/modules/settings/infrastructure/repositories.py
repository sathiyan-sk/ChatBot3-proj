from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.settings.domain.entities import PlatformSettings
from app.modules.settings.domain.repository_interfaces import SettingsRepositoryInterface
from app.modules.settings.infrastructure.mappers import map_settings_model_to_entity
from app.modules.settings.infrastructure.orm_models import SettingsModel


class SqlAlchemySettingsRepository(SettingsRepositoryInterface):
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
    ) -> PlatformSettings:
        model = SettingsModel(
            application_id=UUID(str(application_id)),
            llm_temperature=llm_temperature,
            max_context_messages=max_context_messages,
            inactivity_timeout_minutes=inactivity_timeout_minutes,
            retention_days=retention_days,
            prompt_system_template=prompt_system_template,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return map_settings_model_to_entity(model)

    def get_by_application_id(self, application_id: str) -> PlatformSettings | None:
        normalized_application_id = UUID(str(application_id))
        statement = select(SettingsModel).where(SettingsModel.application_id == normalized_application_id)
        model = self._session.execute(statement).scalar_one_or_none()
        return None if model is None else map_settings_model_to_entity(model)

    def update(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
    ) -> PlatformSettings:
        statement = select(SettingsModel).where(
            SettingsModel.application_id == UUID(str(application_id))
        )
        model = self._session.execute(statement).scalar_one()

        model.llm_temperature = llm_temperature
        model.max_context_messages = max_context_messages
        model.inactivity_timeout_minutes = inactivity_timeout_minutes
        model.retention_days = retention_days
        model.prompt_system_template = prompt_system_template

        self._session.flush()
        self._session.refresh(model)
        return map_settings_model_to_entity(model)