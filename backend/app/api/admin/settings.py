from __future__ import annotations
from dataclasses import asdict
from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_settings_application_service
from app.api.schemas.settings import (
    CreateSettingsRequest,
    SettingsResponse,
    UpdateSettingsRequest,
)
from app.modules.settings.application.commands import (
    CreateSettingsCommand,
    UpdateSettingsCommand,
)
from app.modules.settings.application.queries import GetSettingsByApplicationQuery
from app.modules.settings.application.services import SettingsApplicationService

router = APIRouter(prefix="/admin/settings", tags=["Admin Settings"])


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
        )
    )
    return SettingsResponse.model_validate(asdict(result))