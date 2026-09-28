from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateWidgetRequest(BaseModel):
    application_id: UUID

    display_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    theme: str = Field(
        default="light",
        min_length=1,
        max_length=50,
    )

    launcher_label: str | None = Field(
        default=None,
        max_length=100,
    )

    welcome_message: str | None = None

    placeholder_text: str | None = Field(
        default=None,
        max_length=255,
    )

    is_enabled: bool = True


class UpdateWidgetRequest(BaseModel):
    display_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
    )

    theme: str = Field(
        default="light",
        min_length=1,
        max_length=50,
    )

    launcher_label: str | None = Field(
        default=None,
        max_length=100,
    )

    welcome_message: str | None = None

    placeholder_text: str | None = Field(
        default=None,
        max_length=255,
    )

    is_enabled: bool = True


class WidgetResponse(BaseModel):
    id: UUID
    application_id: UUID
    display_name: str
    public_key: str | None
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }



class PublicWidgetConfigurationResponse(BaseModel):
    display_name: str
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    is_enabled: bool


class WidgetSessionRequest(BaseModel):
    conversation_identity: str = Field(..., min_length=1, max_length=255)


class WidgetSessionMessage(BaseModel):
    role: str
    content: str
    created_at: datetime


class WidgetSessionResponse(BaseModel):
    conversation_id: str
    messages: list[WidgetSessionMessage] = Field(default_factory=list)