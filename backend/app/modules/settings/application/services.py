from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ApplicationError
from app.modules.settings.application.commands import CreateSettingsCommand, UpdateSettingsCommand
from app.modules.settings.application.dto import SettingsDto
from app.modules.settings.application.queries import GetSettingsByApplicationQuery
from app.modules.settings.domain.entities import PlatformSettings
from app.modules.settings.domain.repository_interfaces import SettingsRepositoryInterface


@dataclass(slots=True)
class SettingsApplicationService:
    settings_repository: SettingsRepositoryInterface

    def create(self, command: CreateSettingsCommand) -> SettingsDto:
        existing = self.settings_repository.get_by_application_id(command.application_id)
        if existing is not None:
            raise ApplicationError(
                message="Settings already exist for this application.",
                code="settings_already_exist",
                status_code=409,
            )

        created = self.settings_repository.create(
            application_id=command.application_id,
            llm_temperature=command.llm_temperature,
            max_context_messages=command.max_context_messages,
            inactivity_timeout_minutes=command.inactivity_timeout_minutes,
            retention_days=command.retention_days,
            prompt_system_template=command.prompt_system_template,
        )
        return self._to_dto(created)

    def get_by_application(self, query: GetSettingsByApplicationQuery) -> SettingsDto:
        settings = self.settings_repository.get_by_application_id(query.application_id)
        if settings is None:
            raise ApplicationError(
                message="Settings not found.",
                code="settings_not_found",
                status_code=404,
            )
        return self._to_dto(settings)

    def update(self, command: UpdateSettingsCommand) -> SettingsDto:
        existing = self.settings_repository.get_by_application_id(command.application_id)
        if existing is None:
            raise ApplicationError(
                message="Settings not found.",
                code="settings_not_found",
                status_code=404,
            )

        updated = self.settings_repository.update(
            application_id=command.application_id,
            llm_temperature=command.llm_temperature,
            max_context_messages=command.max_context_messages,
            inactivity_timeout_minutes=command.inactivity_timeout_minutes,
            retention_days=command.retention_days,
            prompt_system_template=command.prompt_system_template,
        )
        return self._to_dto(updated)

    def _to_dto(self, settings: PlatformSettings) -> SettingsDto:
        return SettingsDto(
            id=str(settings.id),
            application_id=str(settings.application_id),
            llm_temperature=settings.llm_temperature,
            max_context_messages=settings.max_context_messages,
            inactivity_timeout_minutes=settings.inactivity_timeout_minutes,
            retention_days=settings.retention_days,
            prompt_system_template=settings.prompt_system_template,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )