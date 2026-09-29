from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(slots=True, frozen=True)
class CreateWidgetCommand:
    application_id: UUID
    display_name: str
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    accent_color: str | None
    starter_prompts: list[str] | None
    is_enabled: bool


@dataclass(slots=True, frozen=True)
class UpdateWidgetCommand:
    widget_id: UUID
    display_name: str
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    accent_color: str | None
    starter_prompts: list[str] | None
    is_enabled: bool
