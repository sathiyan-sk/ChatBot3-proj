from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


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

    accent_color: str | None = Field(
        default=None,
        max_length=20,
    )

    starter_prompts: list[str] | None = Field(
        default=None,
        max_length=20,
    )

    is_enabled: bool = True

    @field_validator("accent_color")
    @classmethod
    def validate_accent_color(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if len(normalized) == 4 and normalized.startswith("#"):
            normalized = "#" + "".join(character * 2 for character in normalized[1:])
        if len(normalized) != 7 or normalized[0] != "#" or any(
            character not in "0123456789ABCDEF" for character in normalized[1:]
        ):
            raise ValueError("Accent color must be a valid #RRGGBB hex value.")
        return normalized

    @field_validator("starter_prompts")
    @classmethod
    def validate_starter_prompts(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None
        if len(values) > 20 or any(len(prompt.strip()) > 200 for prompt in values):
            raise ValueError("Provide at most 20 starter prompts, each 200 characters or fewer.")
        return values


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

    accent_color: str | None = Field(
        default=None,
        max_length=20,
    )

    starter_prompts: list[str] | None = Field(
        default=None,
        max_length=20,
    )

    is_enabled: bool = True

    @field_validator("accent_color")
    @classmethod
    def validate_accent_color(cls, value: str | None) -> str | None:
        return CreateWidgetRequest.validate_accent_color(value)

    @field_validator("starter_prompts")
    @classmethod
    def validate_starter_prompts(
        cls,
        values: list[str] | None,
    ) -> list[str] | None:
        return CreateWidgetRequest.validate_starter_prompts(values)


class WidgetResponse(BaseModel):
    id: UUID
    application_id: UUID
    display_name: str
    public_key: str | None
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    accent_color: str | None = None
    starter_prompts: list[str] | None = None
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
    accent_color: str | None = None
    starter_prompts: list[str] = Field(default_factory=list)
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