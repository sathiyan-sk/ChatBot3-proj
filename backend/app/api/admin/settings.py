from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import get_settings_application_service
from app.api.schemas.settings import (
    CreateSettingsRequest,
    ProviderCatalogResponse,
    ProviderModelOptionResponse,
    ConfigurationCapabilityCheckResponse,
    ConfigurationValidationResponse,
    SettingsResponse,
    UpdateSettingsRequest,
)
from app.config.provider_registry import (
    build_provider_catalog,
    is_supported_selection,
)
from app.modules.settings.application.commands import (
    CreateSettingsCommand,
    UpdateSettingsCommand,
)
from app.modules.settings.application.queries import GetSettingsByApplicationQuery
from app.modules.settings.application.services import SettingsApplicationService

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


@router.post(
    "/by-application/{application_id}/validate",
    response_model=ConfigurationValidationResponse,
)
def validate_application_configuration(
    application_id: str,
    service: SettingsApplicationService = Depends(get_settings_application_service),
) -> ConfigurationValidationResponse:
    settings = service.get_by_application(
        GetSettingsByApplicationQuery(application_id=application_id)
    )
    selections = (
        ("parser", settings.parser_provider, None),
        ("embedding", settings.embedding_provider, settings.embedding_model),
        ("llm", settings.llm_provider, settings.llm_model),
    )
    checks = []
    for capability, provider, model in selections:
        ready = is_supported_selection(
            service.provider_catalog,
            capability=capability,
            provider=provider or "",
            model=model,
        )
        checks.append(
            ConfigurationCapabilityCheckResponse(
                capability=capability,
                provider=provider or "",
                model=model,
                ready=ready,
                message=(
                    "Selection is enabled by the platform and required backend "
                    "credentials are configured."
                    if ready
                    else (
                        "Selection is unavailable in the platform catalog. "
                        "Check provider enablement, credentials, and model settings."
                    )
                ),
            )
        )
    return ConfigurationValidationResponse(
        application_id=application_id,
        ready=all(check.ready for check in checks),
        checks=checks,
        checked_at=datetime.now(timezone.utc),
    )


@router.get("/provider-catalog", response_model=ProviderCatalogResponse)
def get_provider_catalog(request: Request) -> ProviderCatalogResponse:
    catalog = build_provider_catalog(request.app.state.settings)
    return ProviderCatalogResponse(
        parsers=[
            ProviderModelOptionResponse(
                provider=option.provider,
                model=option.model,
                label=option.label,
                embedding_dimensions=option.embedding_dimensions,
            )
            for option in catalog.parsers
        ],
        embeddings=[
            ProviderModelOptionResponse(
                provider=option.provider,
                model=option.model,
                label=option.label,
                embedding_dimensions=option.embedding_dimensions,
            )
            for option in catalog.embeddings
        ],
        llms=[
            ProviderModelOptionResponse(
                provider=option.provider,
                model=option.model,
                label=option.label,
                embedding_dimensions=option.embedding_dimensions,
            )
            for option in catalog.llms
        ],
    )


@router.post("", response_model=SettingsResponse, status_code=status.HTTP_201_CREATED)
def create_settings(
    request: CreateSettingsRequest,
    service: SettingsApplicationService = Depends(get_settings_application_service),
) -> SettingsResponse:
    result = service.create(
        CreateSettingsCommand(
            application_id=request.application_id,
            llm_temperature=str(request.llm_temperature),
            max_context_messages=request.max_context_messages,
            inactivity_timeout_minutes=request.inactivity_timeout_minutes,
            retention_days=request.retention_days,
            prompt_system_template=request.prompt_system_template,
            parser_provider=request.parser_provider,
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
        )
    )
    return SettingsResponse.model_validate(asdict(result))


@router.get("/by-application/{application_id}", response_model=SettingsResponse)
def get_settings_by_application(
    application_id: str,
    service: SettingsApplicationService = Depends(get_settings_application_service),
) -> SettingsResponse:
    result = service.get_by_application(
        GetSettingsByApplicationQuery(application_id=application_id)
    )
    data = asdict(result)
    data["id"] = str(data["id"])
    data["application_id"] = str(data["application_id"])
    return SettingsResponse.model_validate(data)


@router.put("/by-application/{application_id}", response_model=SettingsResponse)
def update_settings(
    application_id: str,
    request: UpdateSettingsRequest,
    service: SettingsApplicationService = Depends(get_settings_application_service),
) -> SettingsResponse:
    result = service.update(
        UpdateSettingsCommand(
            application_id=application_id,
            llm_temperature=str(request.llm_temperature),
            max_context_messages=request.max_context_messages,
            inactivity_timeout_minutes=request.inactivity_timeout_minutes,
            retention_days=request.retention_days,
            prompt_system_template=request.prompt_system_template,
            parser_provider=request.parser_provider,
            embedding_provider=request.embedding_provider,
            embedding_model=request.embedding_model,
            llm_provider=request.llm_provider,
            llm_model=request.llm_model,
        )
    )
    return SettingsResponse.model_validate(asdict(result))
