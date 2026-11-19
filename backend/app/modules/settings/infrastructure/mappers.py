from __future__ import annotations

from app.infrastructure.db.models.settings_model import SettingsModel
from app.modules.settings.domain.entities import PlatformSettings


def map_settings_model_to_entity(model: SettingsModel) -> PlatformSettings:
    return PlatformSettings(
        id=model.id,
        application_id=model.application_id,
        llm_temperature=model.llm_temperature,
        max_context_messages=model.max_context_messages,
        inactivity_timeout_minutes=model.inactivity_timeout_minutes,
        retention_days=model.retention_days,
        prompt_system_template=model.prompt_system_template,
        parser_provider=model.parser_provider,
        embedding_provider=model.embedding_provider,
        embedding_model=model.embedding_model,
        llm_provider=model.llm_provider,
        llm_model=model.llm_model,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )