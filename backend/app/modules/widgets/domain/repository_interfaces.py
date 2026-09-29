from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.widgets.domain.entities import Widget


class WidgetRepositoryInterface(ABC):
    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def get_by_public_key(
    self,
    public_key: str,
) -> Widget | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_id(
        self,
        widget_id: UUID | str,
    ) -> Widget | None:
        raise NotImplementedError

    @abstractmethod
    def get_by_application_id(
        self,
        application_id: UUID | str,
    ) -> Widget | None:
        raise NotImplementedError

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def delete(
        self,
        widget_id: UUID | str,
    ) -> None:
        raise NotImplementedError
