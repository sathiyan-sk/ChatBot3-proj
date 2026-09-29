from __future__ import annotations

from app.infrastructure.db.models.widget_model import (
    WidgetModel,
)
from app.modules.widgets.domain.entities import Widget


def map_widget_model_to_entity(
    model: WidgetModel,
) -> Widget:
    return Widget(
        id=model.id,
        application_id=model.application_id,
        display_name=model.display_name,
        public_key=model.public_key,
        theme=model.theme,
        launcher_label=model.launcher_label,
        welcome_message=model.welcome_message,
        placeholder_text=model.placeholder_text,
        accent_color=model.accent_color,
        starter_prompts=model.starter_prompts,
        is_enabled=model.is_enabled,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )