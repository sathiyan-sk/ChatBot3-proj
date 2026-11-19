from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class SettingsDto:
    id: str
    application_id: str
    llm_temperature: str
    max_context_messages: int
    inactivity_timeout_minutes: int
    retention_days: int
    prompt_system_template: str | None
    parser_provider: str | None
    embedding_provider: str | None
    embedding_model: str | None
    llm_provider: str | None
    llm_model: str | None
    embedding_change_allowed: bool
    created_at: datetime
    updated_at: datetime