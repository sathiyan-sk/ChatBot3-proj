from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CreateSettingsCommand:
    application_id: str
    llm_temperature: str = "0.2"
    max_context_messages: int = 12
    inactivity_timeout_minutes: int = 30
    retention_days: int = 30
    prompt_system_template: str | None = None
    parser_provider: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None


@dataclass(slots=True, frozen=True)
class UpdateSettingsCommand:
    application_id: str
    llm_temperature: str
    max_context_messages: int
    inactivity_timeout_minutes: int
    retention_days: int
    prompt_system_template: str | None = None
    parser_provider: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None