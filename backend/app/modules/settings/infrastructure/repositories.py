from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.modules.settings.domain.entities import PlatformSettings
from app.modules.settings.domain.repository_interfaces import SettingsRepositoryInterface
from app.modules.settings.infrastructure.mappers import map_settings_model_to_entity
from app.modules.settings.infrastructure.orm_models import SettingsModel


class SqlAlchemySettingsRepository(SettingsRepositoryInterface):
    def __init__(
        self,
        session: Session,
        *,
        vector_store_table_name: str = "document_chunks",
    ) -> None:
        self._session = session
        self._vector_store_table_name = vector_store_table_name

    def create(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
        parser_provider: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> PlatformSettings:
        model = SettingsModel(
            application_id=UUID(str(application_id)),
            llm_temperature=llm_temperature,
            max_context_messages=max_context_messages,
            inactivity_timeout_minutes=inactivity_timeout_minutes,
            retention_days=retention_days,
            prompt_system_template=prompt_system_template,
            parser_provider=parser_provider,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)
        return map_settings_model_to_entity(model)

    def get_by_application_id(self, application_id: str) -> PlatformSettings | None:
        normalized_application_id = UUID(str(application_id))
        statement = select(SettingsModel).where(SettingsModel.application_id == normalized_application_id)
        model = self._session.execute(statement).scalar_one_or_none()
        return None if model is None else map_settings_model_to_entity(model)

    def get_by_application_id_for_update(
        self,
        application_id: str,
    ) -> PlatformSettings | None:
        statement = (
            select(SettingsModel)
            .where(SettingsModel.application_id == UUID(str(application_id)))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = self._session.execute(statement).scalar_one_or_none()
        return None if model is None else map_settings_model_to_entity(model)

    def has_published_vectors(self, application_id: str) -> bool:
        statement = text(
            f"""
            select exists (
                select 1
                from documents as document
                where document.application_id = cast(:application_id as uuid)
                  and document.ready_version is not null
                  and exists (
                      select 1
                      from {self._vector_store_table_name} as chunk
                      where chunk.document_id = cast(document.id as text)
                        and chunk.knowledge_base_id = cast(document.knowledge_base_id as text)
                        and chunk.ingestion_version = document.ready_version
                  )
            )
            """
        )
        return bool(
            self._session.execute(
                statement,
                {"application_id": str(application_id)},
            ).scalar_one()
        )

    def update(
        self,
        *,
        application_id: str,
        llm_temperature: str,
        max_context_messages: int,
        inactivity_timeout_minutes: int,
        retention_days: int,
        prompt_system_template: str | None,
        parser_provider: str | None,
        embedding_provider: str | None,
        embedding_model: str | None,
        llm_provider: str | None,
        llm_model: str | None,
    ) -> PlatformSettings:
        statement = (
            select(SettingsModel)
            .where(SettingsModel.application_id == UUID(str(application_id)))
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        model = self._session.execute(statement).scalar_one()

        model.llm_temperature = llm_temperature
        model.max_context_messages = max_context_messages
        model.inactivity_timeout_minutes = inactivity_timeout_minutes
        model.retention_days = retention_days
        model.prompt_system_template = prompt_system_template
        model.parser_provider = parser_provider
        model.embedding_provider = embedding_provider
        model.embedding_model = embedding_model
        model.llm_provider = llm_provider
        model.llm_model = llm_model

        self._session.flush()
        self._session.refresh(model)
        return map_settings_model_to_entity(model)