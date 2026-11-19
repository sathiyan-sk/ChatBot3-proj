from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.config.provider_registry import (
    build_provider_catalog,
    is_supported_selection,
    platform_default_selection,
)
from app.core.exceptions import ApplicationError
from app.modules.applications.application.commands import (
    CreateApplicationCommand,
    UpdateApplicationCommand,
)
from app.modules.applications.application.dto import ApplicationDto, CreatedApplicationDto
from app.modules.applications.domain.entities import Application
from app.modules.applications.domain.policies import (
    build_application_slug,
    normalize_application_name,
    normalize_optional_text,
)
from app.modules.applications.domain.repository_interfaces import (
    ApplicationProvisioningRepository,
    ApplicationRepository,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApplicationServices:
    session: Session
    application_repository: ApplicationRepository
    provisioning_repository: ApplicationProvisioningRepository
    platform_settings: Settings

    def create_application(self, command: CreateApplicationCommand) -> CreatedApplicationDto:
        normalized_name = normalize_application_name(command.name)
        slug = build_application_slug(normalized_name)
        description = normalize_optional_text(command.description)
        allowed_origins = self._normalize_allowed_origins(command.allowed_origins)

        existing_by_slug = self.application_repository.get_by_slug(slug)
        if existing_by_slug is not None:
            raise ApplicationError(
                message=f"Application slug '{slug}' already exists.",
                code="application_slug_exists",
                status_code=409,
            )

        parser_provider, parser_model = platform_default_selection(
            self.platform_settings,
            capability="parser",
        )
        embedding_provider, embedding_model = platform_default_selection(
            self.platform_settings,
            capability="embedding",
        )
        llm_provider, llm_model = platform_default_selection(
            self.platform_settings,
            capability="llm",
        )
        catalog = build_provider_catalog(self.platform_settings)
        defaults = (
            ("parser", parser_provider, parser_model),
            ("embedding", embedding_provider, embedding_model),
            ("llm", llm_provider, llm_model),
        )
        if any(
            not is_supported_selection(
                catalog,
                capability=capability,
                provider=provider,
                model=model,
            )
            for capability, provider, model in defaults
        ):
            raise ApplicationError(
                message=(
                    "The platform's default provider/model selection is not "
                    "available in the enabled provider catalog."
                ),
                code="platform_provider_default_unsupported",
                status_code=503,
            )

        application = self.application_repository.create(
            name=normalized_name,
            slug=slug,
            description=description,
            client_type=command.client_type.strip(),
            allowed_origins=allowed_origins,
        )

        key_material = self._generate_api_key_material(slug=slug)

        self.provisioning_repository.create_default_knowledge_base(
            application_id=str(application.id),
            application_name=application.name,
        )
        self.provisioning_repository.create_default_settings(
            application_id=str(application.id),
            parser_provider=parser_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model or "",
            llm_provider=llm_provider,
            llm_model=llm_model or "",
        )
        self.provisioning_repository.create_api_key(
            application_id=str(application.id),
            key_name="Default API Key",
            key_prefix=key_material["key_prefix"],
            key_hash=key_material["key_hash"],
        )

        self.session.commit()

        logger.info(
            "Application created and provisioned | application_id=%s slug=%s client_type=%s",
            application.id,
            application.slug,
            application.client_type,
        )

        return CreatedApplicationDto(
            application=self._to_dto(self._require_application(application.id)),
            api_key=key_material["raw_key"],
            api_key_prefix=key_material["key_prefix"],
        )

    def list_applications(self) -> list[ApplicationDto]:
        return [self._to_dto(item) for item in self.application_repository.list_all()]

    def get_application(self, application_id: str) -> ApplicationDto:
        application = self._require_application(application_id)
        return self._to_dto(application)

    def update_application(self, command: UpdateApplicationCommand) -> ApplicationDto:
        current = self._require_application(command.application_id)
        normalized_name = normalize_application_name(command.name)
        next_slug = build_application_slug(normalized_name)
        allowed_origins = self._normalize_allowed_origins(command.allowed_origins)

        if next_slug != current.slug:
            existing_by_slug = self.application_repository.get_by_slug(next_slug)
            if existing_by_slug is not None and existing_by_slug.id != current.id:
                raise ApplicationError(
                    message=f"Application slug '{next_slug}' already exists.",
                    code="application_slug_exists",
                    status_code=409,
                )

        updated = self.application_repository.update(
            application_id=command.application_id,
            name=normalized_name,
            slug=next_slug,
            description=normalize_optional_text(command.description),
            client_type=command.client_type.strip(),
            allowed_origins=allowed_origins,
            is_active=command.is_active,
        )

        self.session.commit()

        logger.info(
            "Application updated | application_id=%s slug=%s is_active=%s",
            updated.id,
            updated.slug,
            updated.is_active,
        )

        return self._to_dto(updated)

    def deactivate_application(self, application_id: str) -> ApplicationDto:
        current = self._require_application(application_id)
        updated = self.application_repository.update(
            application_id=current.id,
            name=current.name,
            slug=current.slug,
            description=current.description,
            client_type=current.client_type,
            allowed_origins=current.allowed_origins,
            is_active=False,
        )
        self.session.commit()

        logger.info("Application deactivated | application_id=%s", updated.id)
        return self._to_dto(updated)

    def _require_application(self, application_id: str) -> Application:
        application = self.application_repository.get_by_id(application_id)
        if application is None:
            raise ApplicationError(
                message="Application not found.",
                code="application_not_found",
                status_code=404,
            )
        return application

    def _normalize_allowed_origins(self, allowed_origins: list[str] | None) -> list[str]:
        if not allowed_origins:
            return []
        cleaned = []
        for origin in allowed_origins:
            value = origin.strip()
            if value:
                cleaned.append(value)
        return cleaned

    def _serialize_allowed_origins(self, allowed_origins: list[str]) -> str | None:
        if not allowed_origins:
            return None
        return ",".join(allowed_origins)

    def _deserialize_allowed_origins(self, raw_value: list[str] | str | None) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, list):
            # Already a list from PostgreSQL text[]
            return [item.strip() for item in raw_value if item and item.strip()]
        # Fallback for legacy string storage
        return [item.strip() for item in raw_value.split(",") if item.strip()]

    def _to_dto(self, application: Application) -> ApplicationDto:
        return ApplicationDto(
            id=str(application.id),
            name=application.name,
            slug=application.slug,
            description=application.description,
            client_type=application.client_type,
            allowed_origins=self._deserialize_allowed_origins(application.allowed_origins),
            is_active=application.is_active,
            created_at=application.created_at,
            updated_at=application.updated_at,
        )

    def _generate_api_key_material(self, *, slug: str) -> dict[str, str]:
        secret_value = secrets.token_urlsafe(32)
        raw_key = f"akp_{slug}_{secret_value}"
        key_prefix = raw_key[:16]
        key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
        return {
            "raw_key": raw_key,
            "key_prefix": key_prefix,
            "key_hash": key_hash,
        }