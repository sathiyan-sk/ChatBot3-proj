from __future__ import annotations

from dataclasses import dataclass

from app.config.provider_registry import (
    ProviderCatalog,
    is_supported_selection,
    platform_default_selection,
)
from app.config.settings import Settings
from app.core.exceptions import ApplicationError
from app.modules.settings.application.commands import CreateSettingsCommand, UpdateSettingsCommand
from app.modules.settings.application.dto import SettingsDto
from app.modules.settings.application.queries import GetSettingsByApplicationQuery
from app.modules.settings.domain.entities import PlatformSettings
from app.modules.settings.domain.repository_interfaces import SettingsRepositoryInterface


@dataclass(slots=True)
class SettingsApplicationService:
    settings_repository: SettingsRepositoryInterface
    platform_settings: Settings
    provider_catalog: ProviderCatalog

    def create(self, command: CreateSettingsCommand) -> SettingsDto:
        existing = self.settings_repository.get_by_application_id(command.application_id)
        if existing is not None:
            raise ApplicationError(
                message="Settings already exist for this application.",
                code="settings_already_exist",
                status_code=409,
            )

        parser_provider = command.parser_provider
        if parser_provider is None:
            parser_provider, _ = platform_default_selection(
                self.platform_settings,
                capability="parser",
            )
        embedding_provider = command.embedding_provider
        embedding_model = command.embedding_model
        if embedding_provider is None or embedding_model is None:
            default_provider, default_model = platform_default_selection(
                self.platform_settings,
                capability="embedding",
            )
            embedding_provider = embedding_provider or default_provider
            embedding_model = embedding_model or default_model
        llm_provider = command.llm_provider
        llm_model = command.llm_model
        if llm_provider is None or llm_model is None:
            default_provider, default_model = platform_default_selection(
                self.platform_settings,
                capability="llm",
            )
            llm_provider = llm_provider or default_provider
            llm_model = llm_model or default_model

        self._validate_selection("parser", parser_provider, None)
        self._validate_selection("embedding", embedding_provider, embedding_model)
        self._validate_selection("llm", llm_provider, llm_model)

        created = self.settings_repository.create(
            application_id=command.application_id,
            llm_temperature=command.llm_temperature,
            max_context_messages=command.max_context_messages,
            inactivity_timeout_minutes=command.inactivity_timeout_minutes,
            retention_days=command.retention_days,
            prompt_system_template=command.prompt_system_template,
            parser_provider=parser_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        return self._to_dto(created, embedding_change_allowed=True)

    def get_by_application(self, query: GetSettingsByApplicationQuery) -> SettingsDto:
        settings = self.settings_repository.get_by_application_id(query.application_id)
        if settings is None:
            raise ApplicationError(
                message="Settings not found.",
                code="settings_not_found",
                status_code=404,
            )
        return self._to_dto(
            settings,
            embedding_change_allowed=not self.settings_repository.has_published_vectors(
                query.application_id
            ),
        )

    def update(self, command: UpdateSettingsCommand) -> SettingsDto:
        existing = self.settings_repository.get_by_application_id_for_update(
            command.application_id
        )
        if existing is None:
            raise ApplicationError(
                message="Settings not found.",
                code="settings_not_found",
                status_code=404,
            )

        current_parser_provider = existing.parser_provider or platform_default_selection(
            self.platform_settings,
            capability="parser",
        )[0]
        current_embedding_provider, current_embedding_model = (
            self._effective_embedding_selection(existing)
        )
        current_llm_provider, current_llm_model = self._effective_llm_selection(existing)

        parser_provider = command.parser_provider or current_parser_provider
        embedding_provider = command.embedding_provider or current_embedding_provider
        embedding_model = command.embedding_model or current_embedding_model
        if command.embedding_provider and not command.embedding_model:
            embedding_model = self._first_model("embedding", embedding_provider)
        llm_provider = command.llm_provider or current_llm_provider
        llm_model = command.llm_model or current_llm_model
        if command.llm_provider and not command.llm_model:
            llm_model = self._first_model("llm", llm_provider)

        parser_changed = parser_provider != current_parser_provider
        embedding_changed = (
            embedding_provider != current_embedding_provider
            or embedding_model != current_embedding_model
        )
        llm_changed = (
            llm_provider != current_llm_provider or llm_model != current_llm_model
        )
        if parser_changed:
            self._validate_selection("parser", parser_provider, None)
        if embedding_changed:
            self._validate_selection(
                "embedding",
                embedding_provider,
                embedding_model,
            )
            if self.settings_repository.has_published_vectors(command.application_id):
                raise ApplicationError(
                    message=(
                        "Embedding provider or model cannot be changed while "
                        "published document vectors exist. Application-wide "
                        "re-embedding support is required first."
                    ),
                    code="embedding_change_requires_reembedding",
                    status_code=409,
                )
        if llm_changed:
            self._validate_selection("llm", llm_provider, llm_model)

        updated = self.settings_repository.update(
            application_id=command.application_id,
            llm_temperature=command.llm_temperature,
            max_context_messages=command.max_context_messages,
            inactivity_timeout_minutes=command.inactivity_timeout_minutes,
            retention_days=command.retention_days,
            prompt_system_template=command.prompt_system_template,
            parser_provider=parser_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        return self._to_dto(
            updated,
            embedding_change_allowed=not self.settings_repository.has_published_vectors(
                command.application_id
            ),
        )

    def _validate_selection(
        self,
        capability: str,
        provider: str | None,
        model: str | None,
    ) -> None:
        if not provider or not is_supported_selection(
            self.provider_catalog,
            capability=capability,
            provider=provider,
            model=model,
        ):
            raise ApplicationError(
                message=(
                    f"Unsupported {capability} provider/model selection: "
                    f"{provider!r}/{model!r}."
                ),
                code="provider_model_selection_unsupported",
                status_code=422,
            )

    def _first_model(self, capability: str, provider: str) -> str | None:
        options = {
            "embedding": self.provider_catalog.embeddings,
            "llm": self.provider_catalog.llms,
        }[capability]
        return next(
            (option.model for option in options if option.provider == provider),
            None,
        )

    def _effective_embedding_selection(
        self,
        settings: PlatformSettings,
    ) -> tuple[str, str | None]:
        default_provider, default_model = platform_default_selection(
            self.platform_settings,
            capability="embedding",
        )
        return (
            settings.embedding_provider or default_provider,
            settings.embedding_model or default_model,
        )

    def _effective_llm_selection(
        self,
        settings: PlatformSettings,
    ) -> tuple[str, str | None]:
        default_provider, default_model = platform_default_selection(
            self.platform_settings,
            capability="llm",
        )
        return settings.llm_provider or default_provider, settings.llm_model or default_model

    def _to_dto(
        self,
        settings: PlatformSettings,
        *,
        embedding_change_allowed: bool,
    ) -> SettingsDto:
        default_parser_provider, _ = platform_default_selection(
            self.platform_settings,
            capability="parser",
        )
        embedding_provider, embedding_model = self._effective_embedding_selection(settings)
        llm_provider, llm_model = self._effective_llm_selection(settings)
        return SettingsDto(
            id=str(settings.id),
            application_id=str(settings.application_id),
            llm_temperature=settings.llm_temperature,
            max_context_messages=settings.max_context_messages,
            inactivity_timeout_minutes=settings.inactivity_timeout_minutes,
            retention_days=settings.retention_days,
            prompt_system_template=settings.prompt_system_template,
            parser_provider=settings.parser_provider or default_parser_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider=llm_provider,
            llm_model=llm_model,
            embedding_change_allowed=embedding_change_allowed,
            created_at=settings.created_at,
            updated_at=settings.updated_at,
        )