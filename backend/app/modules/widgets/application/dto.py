from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(slots=True, frozen=True)
class WidgetDto:
    id: UUID
    application_id: UUID
    display_name: str
    public_key: str | None
    theme: str
    launcher_label: str | None
    welcome_message: str | None
    placeholder_text: str | None
    accent_color: str | None
    starter_prompts: list[str] | None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime
