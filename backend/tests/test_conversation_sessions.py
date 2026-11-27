from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ApplicationError
from app.infrastructure.db.models.conversation_model import ConversationModel
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
    UpdateConversationCommand,
)
from app.modules.conversations.application.commands import ResolveConversationCommand
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
)


class _ConversationRepository:
    def __init__(self, existing):
        self.existing = existing
        self.created = []
        self.updated = []

    def get_active_by_identity(self, **_kwargs):
        return self.existing

    def get_by_id(self, conversation_id):
        if self.existing and self.existing.id == conversation_id:
            return self.existing
        return None

    def get_by_id_and_application_id(self, *, conversation_id, application_id):
        conversation = self.get_by_id(conversation_id)
        if conversation and conversation.application_id == application_id:
            return conversation
        return None

    def update(self, **values):
        self.updated.append(values)
        return SimpleNamespace(
            id=values["conversation_id"],
            application_id="app-id",
            conversation_identity="visitor-id",
            title=values["title"],
            summary=values["summary"],
            is_active=values["is_active"],
            created_at=self.existing.created_at,
            updated_at=datetime.now(timezone.utc),
        )

    def create(self, **values):
        conversation = SimpleNamespace(
            id="new-conversation",
            application_id=values["application_id"],
            conversation_identity=values["conversation_identity"],
            title=values["title"],
            summary=values["summary"],
            is_active=values["is_active"],
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.created.append(values)
        return conversation


def _existing_conversation(last_activity):
    return SimpleNamespace(
        id="old-conversation",
        application_id="app-id",
        conversation_identity="visitor-id",
        title="Website chat",
        summary=None,
        is_active=True,
        created_at=last_activity,
        updated_at=last_activity,
    )


def _service(repository, last_activity=None):
    return ConversationApplicationService(
        conversation_repository=repository,
        message_repository=SimpleNamespace(
            get_last_activity_at=lambda _conversation_id: last_activity
        ),
    )


def test_inactivity_timeout_closes_old_session_and_starts_fresh_one():
    last_activity = datetime.now(timezone.utc) - timedelta(minutes=10)
    repository = _ConversationRepository(
        _existing_conversation(last_activity)
    )

    conversation = _service(repository, last_activity).resolve_conversation(
        ResolveConversationCommand(
            application_id="app-id",
            conversation_identity="visitor-id",
            title="Website chat",
            inactivity_timeout_minutes=5,
        )
    )

    assert repository.updated[0]["conversation_id"] == "old-conversation"
    assert repository.updated[0]["is_active"] is False
    assert len(repository.created) == 1
    assert conversation.id == "new-conversation"


def test_inactivity_timeout_uses_message_activity_not_conversation_updates():
    now = datetime.now(timezone.utc)
    conversation = _existing_conversation(now - timedelta(minutes=10))
    conversation.updated_at = now
    repository = _ConversationRepository(conversation)

    _service(repository, now - timedelta(minutes=10)).resolve_conversation(
        ResolveConversationCommand(
            application_id="app-id",
            conversation_identity="visitor-id",
            title="Website chat",
            inactivity_timeout_minutes=5,
        )
    )

    assert repository.updated[0]["is_active"] is False


def test_recent_message_activity_keeps_conversation_open():
    now = datetime.now(timezone.utc)
    conversation = _existing_conversation(now - timedelta(days=1))
    conversation.updated_at = now - timedelta(days=1)
    repository = _ConversationRepository(conversation)

    result = _service(repository, now).resolve_conversation(
        ResolveConversationCommand(
            application_id="app-id",
            conversation_identity="visitor-id",
            title="Website chat",
            inactivity_timeout_minutes=5,
        )
    )

    assert result.id == conversation.id
    assert repository.updated == []


def test_sandbox_can_preserve_active_session_without_inactivity_timeout():
    repository = _ConversationRepository(
        _existing_conversation(
            datetime.now(timezone.utc) - timedelta(days=30)
        )
    )

    conversation = _service(repository).resolve_conversation(
        ResolveConversationCommand(
            application_id="app-id",
            conversation_identity="visitor-id",
            inactivity_timeout_minutes=None,
        )
    )

    assert conversation.id == "old-conversation"
    assert repository.updated == []
    assert repository.created == []


def test_closing_conversation_preserves_title_and_summary():
    existing = _existing_conversation(datetime.now(timezone.utc))
    existing = SimpleNamespace(**{**vars(existing), "summary": "Conversation context"})
    repository = _ConversationRepository(existing)

    conversation = _service(repository).close_conversation(
        application_id="app-id",
        conversation_id=existing.id,
    )

    assert repository.updated == [
        {
            "conversation_id": existing.id,
            "title": existing.title,
            "summary": existing.summary,
            "is_active": False,
        }
    ]
    assert conversation.title == existing.title
    assert conversation.summary == existing.summary
    assert conversation.is_active is False


def test_update_without_status_preserves_closed_state():
    existing = _existing_conversation(datetime.now(timezone.utc))
    existing = SimpleNamespace(**{**vars(existing), "is_active": False})
    repository = _ConversationRepository(existing)

    conversation = _service(repository).update_conversation(
        UpdateConversationCommand(
            conversation_id=existing.id,
            title=None,
            summary=None,
        )
    )

    assert repository.updated[0]["is_active"] is False
    assert repository.updated[0]["title"] == existing.title
    assert repository.updated[0]["summary"] == existing.summary
    assert conversation.is_active is False


def test_inactive_conversation_rejects_new_messages():
    inactive = _existing_conversation(datetime.now(timezone.utc))
    inactive = SimpleNamespace(**{**vars(inactive), "is_active": False})
    repository = _ConversationRepository(inactive)

    with pytest.raises(ApplicationError) as error:
        _service(repository).append_message(
            AppendMessageCommand(
                conversation_id=inactive.id,
                role="user",
                content="This must not be stored.",
            )
        )

    assert error.value.code == "conversation_inactive"


def test_wrong_application_cannot_read_or_mutate_conversation():
    existing = _existing_conversation(datetime.now(timezone.utc))
    repository = _ConversationRepository(existing)
    service = _service(repository)

    with pytest.raises(ApplicationError) as detail_error:
        service.get_conversation_detail(
            SimpleNamespace(
                conversation_id=existing.id,
                application_id="another-app",
            )
        )
    assert detail_error.value.code == "conversation_not_found"

    with pytest.raises(ApplicationError) as close_error:
        service.close_conversation(
            application_id="another-app",
            conversation_id=existing.id,
        )
    assert close_error.value.code == "conversation_not_found"

    with pytest.raises(ApplicationError) as update_error:
        service.update_conversation(
            UpdateConversationCommand(
                conversation_id=existing.id,
                title="Changed",
                summary=None,
                application_id="another-app",
            )
        )
    assert update_error.value.code == "conversation_not_found"

    with pytest.raises(ApplicationError) as append_error:
        service.append_message(
            AppendMessageCommand(
                conversation_id=existing.id,
                role="user",
                content="Cross-application write",
                application_id="another-app",
            )
        )
    assert append_error.value.code == "conversation_not_found"


def test_closed_conversation_cannot_be_reopened():
    existing = _existing_conversation(datetime.now(timezone.utc))
    existing.is_active = False

    with pytest.raises(ApplicationError) as error:
        _service(_ConversationRepository(existing)).update_conversation(
            UpdateConversationCommand(
                conversation_id=existing.id,
                title=None,
                summary=None,
                is_active=True,
                application_id="app-id",
            )
        )

    assert error.value.code == "conversation_closed"


def test_repository_records_close_time_only_on_active_to_closed_transition():
    now = datetime.now(timezone.utc)
    model = ConversationModel(
        id=uuid4(),
        application_id=uuid4(),
        conversation_identity="visitor-id",
        title="Website chat",
        summary=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )

    class _Session:
        def execute(self, _statement):
            return SimpleNamespace(scalar_one=lambda: model)

        def flush(self):
            pass

        def refresh(self, _model):
            pass

    repository = SqlAlchemyConversationRepository(_Session())
    repository.update(
        conversation_id=str(model.id),
        title=model.title,
        summary=model.summary,
        is_active=False,
    )
    closed_at = model.closed_at

    repository.update(
        conversation_id=str(model.id),
        title="Updated title",
        summary=model.summary,
        is_active=False,
    )

    assert closed_at is not None
    assert model.closed_at == closed_at


def test_concurrent_active_conversation_creation_returns_the_winning_session():
    active_model = ConversationModel(
        id=uuid4(),
        application_id=uuid4(),
        conversation_identity="visitor-id",
        title="Website chat",
        summary=None,
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    class _NestedTransaction:
        def __enter__(self):
            return self

        def __exit__(self, _exc_type, _exc_value, _traceback):
            return False

    class _Session:
        def begin_nested(self):
            return _NestedTransaction()

        def add(self, _model):
            pass

        def flush(self):
            raise IntegrityError("insert conversation", {}, Exception("unique"))

        def execute(self, _statement):
            return SimpleNamespace(
                scalar_one_or_none=lambda: active_model,
            )

    conversation = SqlAlchemyConversationRepository(_Session()).create(
        application_id=str(active_model.application_id),
        conversation_identity="visitor-id",
        title="Website chat",
        summary=None,
        is_active=True,
    )

    assert str(conversation.id) == str(active_model.id)
