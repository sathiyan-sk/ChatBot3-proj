from __future__ import annotations

from uuid import UUID

from sqlalchemy import (
    delete as sqlalchemy_delete,
    select,
)
from sqlalchemy.orm import Session

from app.infrastructure.db.models.widget_model import (
    WidgetModel,
)
from app.modules.widgets.domain.entities import Widget
from app.modules.widgets.domain.repository_interfaces import (
    WidgetRepositoryInterface,
)
from app.modules.widgets.infrastructure.mappers import (
    map_widget_model_to_entity,
)


class SqlAlchemyWidgetRepository(
    WidgetRepositoryInterface,
):
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        *,
        application_id: UUID | str,
        display_name: str,
        public_key: str,
        theme: str,
        launcher_label: str | None,
        welcome_message: str | None,
        placeholder_text: str | None,
        accent_color: str | None,
        starter_prompts: list[str] | None,
        is_enabled: bool,
    ) -> Widget:
        model = WidgetModel(
            application_id=str(
                application_id,
            ),
            display_name=display_name,
            public_key=public_key,
            theme=theme,
            launcher_label=launcher_label,
            welcome_message=welcome_message,
            placeholder_text=placeholder_text,
            accent_color=accent_color,
            starter_prompts=starter_prompts,
            is_enabled=is_enabled,
        )

        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)

        return map_widget_model_to_entity(model)

    def get_by_id(
        self,
        widget_id: UUID | str,
    ) -> Widget | None:
        statement = select(WidgetModel).where(
            WidgetModel.id == str(widget_id),
        )

        model = self._session.execute(
            statement,
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_widget_model_to_entity(model)

    def get_by_application_id(
        self,
        application_id: UUID | str,
    ) -> Widget | None:
        statement = select(WidgetModel).where(
            WidgetModel.application_id
            == str(application_id),
        )

        model = self._session.execute(
            statement,
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_widget_model_to_entity(model)

    def get_by_public_key(
        self,
        public_key: str,
    ) -> Widget | None:
        normalized_key = public_key.strip()

        if not normalized_key:
            return None

        statement = select(WidgetModel).where(
            WidgetModel.public_key
            == normalized_key,
        )

        model = self._session.execute(
            statement,
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_widget_model_to_entity(model)

    def update(
        self,
        *,
        widget_id: UUID | str,
        display_name: str,
        theme: str,
        launcher_label: str | None,
        welcome_message: str | None,
        placeholder_text: str | None,
        accent_color: str | None,
        starter_prompts: list[str] | None,
        is_enabled: bool,
    ) -> Widget:
        statement = select(WidgetModel).where(
            WidgetModel.id == str(widget_id),
        )

        model = self._session.execute(
            statement,
        ).scalar_one_or_none()

        if model is None:
            raise LookupError(
                "Widget not found."
            )

        model.display_name = display_name
        model.theme = theme
        model.launcher_label = launcher_label
        model.welcome_message = welcome_message
        model.placeholder_text = placeholder_text
        model.accent_color = accent_color
        model.starter_prompts = starter_prompts
        model.is_enabled = is_enabled

        self._session.flush()
        self._session.refresh(model)

        return map_widget_model_to_entity(model)

    def delete(
        self,
        widget_id: UUID | str,
    ) -> None:
        statement = sqlalchemy_delete(
            WidgetModel,
        ).where(
            WidgetModel.id == str(widget_id),
        )

        self._session.execute(statement)
        self._session.flush()