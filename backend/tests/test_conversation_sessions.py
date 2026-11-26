from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.modules.conversations.application.commands import ResolveConversationCommand
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)


class _ConversationRepository:
    def __init__(self, existing):
        self.existing = existing
        self.created = []
        self.updated = []

    def get_active_by_identity(self, **_kwargs):
        return self.existing

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


def _service(repository):
    return ConversationApplicationService(
        conversation_repository=repository,
        message_repository=SimpleNamespace(),
    )


def test_inactivity_timeout_closes_old_session_and_starts_fresh_one():
    repository = _ConversationRepository(
        _existing_conversation(
            datetime.now(timezone.utc) - timedelta(minutes=10)
        )
    )

    conversation = _service(repository).resolve_conversation(
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
