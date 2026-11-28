from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.schemas.widgets import CreateWidgetRequest, UpdateWidgetRequest
from app.modules.widgets.application.services import WidgetApplicationService
from app.modules.widgets.domain.entities import Widget


def test_widget_create_and_update_accept_only_supported_themes():
    create_payload = {
        "application_id": uuid4(),
        "display_name": "Support",
        "theme": "dark",
    }
    update_payload = {
        "display_name": "Support",
        "theme": "light",
    }

    assert CreateWidgetRequest(**create_payload).theme == "dark"
    assert UpdateWidgetRequest(**update_payload).theme == "light"

    with pytest.raises(ValidationError):
        CreateWidgetRequest(**{**create_payload, "theme": "system"})

    with pytest.raises(ValidationError):
        UpdateWidgetRequest(**{**update_payload, "theme": "system"})


def test_widget_greeting_message_is_limited_to_1000_characters():
    valid_greeting = "A" * 1000
    create_payload = {
        "application_id": uuid4(),
        "display_name": "Support",
        "welcome_message": valid_greeting,
    }
    update_payload = {
        "display_name": "Support",
        "welcome_message": valid_greeting,
    }

    assert CreateWidgetRequest(**create_payload).welcome_message == valid_greeting
    assert UpdateWidgetRequest(**update_payload).welcome_message == valid_greeting

    with pytest.raises(ValidationError):
        CreateWidgetRequest(**{**create_payload, "welcome_message": valid_greeting + "A"})

    with pytest.raises(ValidationError):
        UpdateWidgetRequest(**{**update_payload, "welcome_message": valid_greeting + "A"})


def test_widget_appearance_options_default_and_validate():
    create_payload = {
        "application_id": uuid4(),
        "display_name": "Support",
    }
    assert CreateWidgetRequest(**create_payload).launcher_position == "right"
    assert CreateWidgetRequest(**create_payload).panel_size == "standard"

    custom_options = {
        **create_payload,
        "launcher_position": "left",
        "panel_size": "wide",
    }
    created = CreateWidgetRequest(**custom_options)
    assert created.launcher_position == "left"
    assert created.panel_size == "wide"

    with pytest.raises(ValidationError):
        CreateWidgetRequest(**{**create_payload, "launcher_position": "center"})
    with pytest.raises(ValidationError):
        UpdateWidgetRequest(
            display_name="Support",
            panel_size="huge",
        )


def test_public_widget_configuration_includes_layout_options():
    now = datetime.now(timezone.utc)
    widget = Widget(
        id=uuid4(),
        application_id=uuid4(),
        display_name="Support",
        public_key="wgt_pub_test",
        theme="dark",
        launcher_position="left",
        panel_size="wide",
        launcher_label="Help",
        welcome_message=None,
        placeholder_text=None,
        accent_color=None,
        starter_prompts=[],
        is_enabled=True,
        created_at=now,
        updated_at=now,
    )
    service = WidgetApplicationService(
        widget_repository=SimpleNamespace(
            get_by_public_key=lambda _key: widget,
        )
    )

    config = service.get_public_configuration("wgt_pub_test")

    assert config["launcher_position"] == "left"
    assert config["panel_size"] == "wide"
