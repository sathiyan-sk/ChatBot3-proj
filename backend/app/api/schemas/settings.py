from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CreateSettingsRequest(BaseModel):
    application_id: str = Field(..., min_length=1)
    llm_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_context_messages: int = Field(default=12, ge=1, le=100)
    inactivity_timeout_minutes: int = Field(default=30, ge=1, le=10080)
    retention_days: int = Field(default=30, ge=1, le=3650)
    prompt_system_template: str | None = Field(default=None, max_length=10000)


class UpdateSettingsRequest(BaseModel):
    llm_temperature: float = Field(..., ge=0.0, le=2.0)
    max_context_messages: int = Field(..., ge=1, le=100)
    inactivity_timeout_minutes: int = Field(..., ge=1, le=10080)
    retention_days: int = Field(..., ge=1, le=3650)
    prompt_system_template: str | None = Field(default=None, max_length=10000)


class SettingsResponse(BaseModel):
    id: str
    application_id: str
    llm_temperature: str
    max_context_messages: int
    inactivity_timeout_minutes: int
    retention_days: int
    prompt_system_template: str | None
    created_at: datetime
    updated_at: datetime