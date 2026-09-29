from __future__ import annotations

import secrets
from dataclasses import dataclass
from uuid import UUID

from app.core.exceptions import ApplicationError
from app.modules.widgets.application.commands import (
    CreateWidgetCommand,
    UpdateWidgetCommand,
)
from app.modules.widgets.application.dto import WidgetDto
from app.modules.widgets.domain.entities import Widget
from app.modules.widgets.domain.repository_interfaces import (
    WidgetRepositoryInterface,
)

DEFAULT_STARTER_PROMPTS = [
    "How do I upgrade my plan?",
    "Reset my API key",
    "What is your refund policy?",
]


@dataclass(slots=True)
class WidgetApplicationService:
    widget_repository: WidgetRepositoryInterface

    def create(
        self,
        command: CreateWidgetCommand,
    ) -> WidgetDto:
        existing = (
            self.widget_repository.get_by_application_id(
                command.application_id,
            )
        )
        public_key = ("wgt_pub_" + secrets.token_urlsafe(32))

        if existing is not None:
            raise ApplicationError(
                message=(
                    "A widget already exists "
                    "for this application."
                ),
                code="widget_already_exists",
                status_code=409,
            )

        created = self.widget_repository.create(
            application_id=command.application_id,
            display_name=(
                command.display_name.strip()
            ),
            public_key=public_key,
            theme=command.theme.strip().lower(),
            launcher_label=self._clean_optional(
                command.launcher_label,
            ),
            welcome_message=self._clean_optional(
                command.welcome_message,
            ),
            placeholder_text=self._clean_optional(
                command.placeholder_text,
            ),
            accent_color=self._clean_optional(
                command.accent_color,
            ),
            starter_prompts=self._clean_prompts(
                command.starter_prompts,
            ),
            is_enabled=command.is_enabled,
        )

        return self._to_dto(created)

    def get_public_configuration(
        self,
        public_key: str,
    ) -> dict[str, object]:
        normalized_key = public_key.strip()

        if not normalized_key:
            raise ApplicationError(
                message="Widget key is required.",
                code="widget_key_required",
                status_code=401,
            )

        widget = (
            self.widget_repository.get_by_public_key(
                normalized_key,
            )
        )

        if widget is None:
            raise ApplicationError(
                message="Invalid widget key.",
                code="invalid_widget_key",
                status_code=401,
            )

        return {
            "display_name": widget.display_name,
            "theme": widget.theme,
            "launcher_label": widget.launcher_label,
            "welcome_message": widget.welcome_message,
            "placeholder_text": widget.placeholder_text,
            "accent_color": widget.accent_color,
            "starter_prompts": (
                DEFAULT_STARTER_PROMPTS.copy()
                if widget.starter_prompts is None
                else widget.starter_prompts
            ),
            "is_enabled": widget.is_enabled,
        }

    def get_by_application_id(
        self,
        application_id: UUID,
    ) -> WidgetDto:
        widget = (
            self.widget_repository.get_by_application_id(
                application_id,
            )
        )

        if widget is None:
            raise ApplicationError(
                message="Widget not found.",
                code="widget_not_found",
                status_code=404,
            )

        return self._to_dto(widget)

    def get_by_id(
        self,
        widget_id: UUID,
    ) -> WidgetDto:
        widget = self.widget_repository.get_by_id(
            widget_id,
        )

        if widget is None:
            raise ApplicationError(
                message="Widget not found.",
                code="widget_not_found",
                status_code=404,
            )

        return self._to_dto(widget)

    def update(
        self,
        command: UpdateWidgetCommand,
    ) -> WidgetDto:
        existing = self.widget_repository.get_by_id(
            command.widget_id,
        )

        if existing is None:
            raise ApplicationError(
                message="Widget not found.",
                code="widget_not_found",
                status_code=404,
            )

        updated = self.widget_repository.update(
            widget_id=command.widget_id,
            display_name=(
                command.display_name.strip()
            ),
            theme=command.theme.strip().lower(),
            launcher_label=self._clean_optional(
                command.launcher_label,
            ),
            welcome_message=self._clean_optional(
                command.welcome_message,
            ),
            placeholder_text=self._clean_optional(
                command.placeholder_text,
            ),
            accent_color=self._clean_optional(
                command.accent_color,
            ),
            starter_prompts=self._clean_prompts(
                command.starter_prompts,
            ),
            is_enabled=command.is_enabled,
        )

        return self._to_dto(updated)

    def delete(
        self,
        widget_id: UUID,
    ) -> None:
        existing = self.widget_repository.get_by_id(
            widget_id,
        )

        if existing is None:
            raise ApplicationError(
                message="Widget not found.",
                code="widget_not_found",
                status_code=404,
            )

        self.widget_repository.delete(widget_id)

    @staticmethod
    def _clean_optional(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @staticmethod
    def _clean_prompts(
        values: list[str] | None,
    ) -> list[str] | None:
        if values is None:
            return None

        cleaned = [
            str(item).strip()
            for item in values
            if item is not None and str(item).strip()
        ]

        return cleaned

    @staticmethod
    def _to_dto(
        widget: Widget,
    ) -> WidgetDto:
        return WidgetDto(
            id=widget.id,
            application_id=widget.application_id,
            display_name=widget.display_name,
            public_key=widget.public_key,
            theme=widget.theme,
            launcher_label=widget.launcher_label,
            welcome_message=widget.welcome_message,
            placeholder_text=widget.placeholder_text,
            accent_color=widget.accent_color,
            starter_prompts=widget.starter_prompts,
            is_enabled=widget.is_enabled,
            created_at=widget.created_at,
            updated_at=widget.updated_at,
        )
