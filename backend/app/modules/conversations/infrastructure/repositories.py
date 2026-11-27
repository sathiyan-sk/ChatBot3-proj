from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.infrastructure.db.models.application_model import ApplicationModel
from app.infrastructure.db.models.conversation_model import (
    ConversationModel,
)
from app.infrastructure.db.models.message_model import (
    MessageModel,
)
from app.infrastructure.db.models.settings_model import SettingsModel
from app.modules.conversations.domain.entities import (
    Conversation,
    ConversationListItem,
    ConversationListPage,
    Message,
)
from app.modules.conversations.domain.repository_interfaces import (
    ConversationRepositoryInterface,
    MessageRepositoryInterface,
)
from app.modules.conversations.infrastructure.mappers import (
    map_conversation_model_to_entity,
    map_message_model_to_entity,
)


class SqlAlchemyConversationRepository(
    ConversationRepositoryInterface
):
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        *,
        application_id: str,
        conversation_identity: str,
        title: str | None,
        summary: str | None,
        is_active: bool,
    ) -> Conversation:
        model = ConversationModel(
            application_id=application_id,
            conversation_identity=(
                conversation_identity
            ),
            title=title,
            summary=summary,
            is_active=is_active,
        )

        try:
            with self._session.begin_nested():
                self._session.add(model)
                self._session.flush()
        except IntegrityError:
            active = self.get_active_by_identity(
                application_id=application_id,
                conversation_identity=conversation_identity,
            )
            if active is None:
                raise
            return active
        self._session.refresh(model)

        return map_conversation_model_to_entity(
            model,
        )

    def get_by_id(
        self,
        conversation_id: str,
    ) -> Conversation | None:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.id
                == conversation_id,
            )
        )

        model = self._session.execute(
            statement
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_conversation_model_to_entity(
            model,
        )

    def get_by_id_and_application_id(
        self,
        *,
        conversation_id: str,
        application_id: str,
    ) -> Conversation | None:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.id
                == conversation_id,
            )
            .where(
                ConversationModel.application_id
                == application_id,
            )
        )

        model = self._session.execute(
            statement
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_conversation_model_to_entity(
            model,
        )

    def get_active_by_identity(
        self,
        *,
        application_id: str,
        conversation_identity: str,
    ) -> Conversation | None:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.application_id
                == application_id,
            )
            .where(
                ConversationModel.conversation_identity
                == conversation_identity,
            )
            .where(
                ConversationModel.is_active.is_(True),
            )
            .order_by(
                ConversationModel.created_at.desc(),
            )
            .limit(1)
        )

        model = self._session.execute(
            statement
        ).scalar_one_or_none()

        if model is None:
            return None

        return map_conversation_model_to_entity(
            model,
        )

    def list_by_application_id(
        self,
        *,
        application_id: str,
        is_active: bool | None,
        activity_from: datetime | None,
        activity_to: datetime | None,
        search: str | None,
        sort_by: str,
        sort_order: str,
        limit: int,
        offset: int,
    ) -> ConversationListPage:
        message_stats = (
            select(
                MessageModel.conversation_id.label("conversation_id"),
                func.count(MessageModel.id).label("message_count"),
                func.max(MessageModel.created_at).label("last_message_at"),
            )
            .join(
                ConversationModel,
                ConversationModel.id == MessageModel.conversation_id,
            )
            .where(ConversationModel.application_id == application_id)
            .group_by(MessageModel.conversation_id)
            .subquery()
        )
        last_activity = func.coalesce(
            message_stats.c.last_message_at,
            ConversationModel.created_at,
        )
        message_count = func.coalesce(message_stats.c.message_count, 0)
        filters = [ConversationModel.application_id == application_id]
        if is_active is not None:
            filters.append(ConversationModel.is_active.is_(is_active))
        if activity_from is not None:
            filters.append(last_activity >= activity_from)
        if activity_to is not None:
            filters.append(last_activity < activity_to)
        if search:
            escaped_search = (
                search.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            search_pattern = f"%{escaped_search}%"
            filters.append(
                ConversationModel.title.ilike(search_pattern, escape="\\")
                | ConversationModel.conversation_identity.ilike(
                    search_pattern,
                    escape="\\",
                )
            )

        joined = ConversationModel.__table__.outerjoin(
            message_stats,
            message_stats.c.conversation_id == ConversationModel.id,
        )
        total = self._session.execute(
            select(func.count(ConversationModel.id))
            .select_from(joined)
            .where(*filters)
        ).scalar_one()

        sort_column = (
            last_activity if sort_by == "activity" else ConversationModel.created_at
        )
        sort_expression = (
            sort_column.asc() if sort_order == "asc" else sort_column.desc()
        )
        rows = self._session.execute(
            select(ConversationModel, last_activity, message_count)
            .select_from(joined)
            .where(*filters)
            .order_by(sort_expression, ConversationModel.id.asc())
            .limit(limit)
            .offset(offset)
        ).all()
        return ConversationListPage(
            items=[
                ConversationListItem(
                    conversation=map_conversation_model_to_entity(model),
                    message_count=int(count),
                    last_activity_at=activity_at,
                )
                for model, activity_at, count in rows
            ],
            total=int(total),
        )

    def list_by_identity(
        self,
        *,
        application_id: str,
        conversation_identity: str,
    ) -> list[Conversation]:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.application_id
                == application_id,
            )
            .where(
                ConversationModel.conversation_identity
                == conversation_identity,
            )
            .order_by(
                ConversationModel.created_at.desc(),
            )
        )

        models = self._session.execute(
            statement
        ).scalars().all()

        return [
            map_conversation_model_to_entity(item)
            for item in models
        ]

    def update(
        self,
        *,
        conversation_id: str,
        title: str | None,
        summary: str | None,
        is_active: bool,
    ) -> Conversation:
        statement = (
            select(ConversationModel)
            .where(
                ConversationModel.id
                == conversation_id,
            )
        )

        model = self._session.execute(
            statement
        ).scalar_one()

        model.title = title
        model.summary = summary
        if model.is_active and not is_active:
            model.closed_at = datetime.now(timezone.utc)
        model.is_active = is_active

        self._session.flush()
        self._session.refresh(model)

        return map_conversation_model_to_entity(
            model,
        )

    def touch_activity(self, conversation_id: str) -> None:
        model = self._session.execute(
            select(ConversationModel).where(
                ConversationModel.id == conversation_id,
            )
        ).scalar_one()
        model.updated_at = datetime.now(timezone.utc)
        self._session.flush()

    def delete_expired_conversations(
        self,
        *,
        default_retention_days: int,
        application_id: str | None = None,
    ) -> int:
        retention_query = select(
            ApplicationModel.id,
            SettingsModel.retention_days,
        ).outerjoin(
                SettingsModel,
                SettingsModel.application_id == ApplicationModel.id,
        )
        if application_id is not None:
            retention_query = retention_query.where(
                ApplicationModel.id == application_id
            )
        retention_rows = self._session.execute(retention_query).all()
        now = datetime.now(timezone.utc)
        deleted_count = 0

        for application_id, configured_days in retention_rows:
            retention_days = configured_days or default_retention_days
            cutoff = now - timedelta(days=retention_days)
            last_message_at = (
                select(func.max(MessageModel.created_at))
                .where(MessageModel.conversation_id == ConversationModel.id)
                .correlate(ConversationModel)
                .scalar_subquery()
            )
            message_or_creation_activity = func.coalesce(
                last_message_at,
                ConversationModel.created_at,
            )
            retention_activity = case(
                (
                    ConversationModel.is_active.is_(False),
                    func.coalesce(
                        ConversationModel.closed_at,
                        message_or_creation_activity,
                    ),
                ),
                else_=message_or_creation_activity,
            )
            result = self._session.execute(
                delete(ConversationModel).where(
                    ConversationModel.application_id == application_id,
                    retention_activity < cutoff,
                    or_(
                        ConversationModel.conversation_identity
                        != f"sandbox-{application_id}",
                        ConversationModel.is_active.is_(False),
                    ),
                )
            )
            deleted_count += result.rowcount or 0

        return deleted_count


class SqlAlchemyMessageRepository(
    MessageRepositoryInterface
):
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def create(
        self,
        *,
        conversation_id: str,
        role: str,
        content: str,
        sequence_number: int,
        citation_payload: str | None,
    ) -> Message:
        model = MessageModel(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sequence_number=sequence_number,
            citations_json=citation_payload,
            metadata_json=None,
        )

        self._session.add(model)
        self._session.flush()
        self._session.refresh(model)

        return map_message_model_to_entity(
            model,
        )

    def list_by_conversation_id(
        self,
        conversation_id: str,
    ) -> list[Message]:
        statement = (
            select(MessageModel)
            .where(
                MessageModel.conversation_id
                == conversation_id,
            )
            .order_by(
                MessageModel.sequence_number.asc(),
            )
        )

        models = self._session.execute(
            statement
        ).scalars().all()

        return [
            map_message_model_to_entity(item)
            for item in models
        ]

    def get_latest_sequence_number(
        self,
        conversation_id: str,
    ) -> int:
        statement = select(
            func.max(
                MessageModel.sequence_number,
            )
        ).where(
            MessageModel.conversation_id
            == conversation_id,
        )

        value = self._session.execute(
            statement
        ).scalar_one_or_none()

        return int(value or 0)

    def get_last_activity_at(self, conversation_id: str) -> datetime | None:
        statement = select(func.max(MessageModel.created_at)).where(
            MessageModel.conversation_id == conversation_id,
        )
        return self._session.execute(statement).scalar_one_or_none()