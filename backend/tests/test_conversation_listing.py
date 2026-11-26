from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from sqlalchemy.dialects import postgresql

from app.api.admin.conversations import list_application_conversations
from app.core.exceptions import ApplicationError
from app.modules.conversations.application.queries import (
    ListApplicationConversationsQuery,
)
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.conversations.domain.entities import (
    Conversation,
    ConversationListItem,
    ConversationListPage,
)
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
)


APPLICATION_ID = "00000000-0000-0000-0000-000000000001"


class _ConversationRepository:
    def __init__(self, page=None):
        self.page = page or ConversationListPage(items=[], total=0)
        self.query = None

    def list_by_application_id(self, **query):
        self.query = query
        return self.page


def _service(repository):
    return ConversationApplicationService(
        conversation_repository=repository,
        message_repository=SimpleNamespace(),
    )


def test_list_conversations_applies_app_scoped_filters_sort_and_pagination():
    created_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
    conversation = Conversation(
        id="00000000-0000-0000-0000-000000000002",
        application_id=APPLICATION_ID,
        conversation_identity="visitor-123",
        title="Pricing",
        summary=None,
        is_active=True,
        created_at=created_at,
        updated_at=created_at,
    )
    repository = _ConversationRepository(
        ConversationListPage(
            items=[
                ConversationListItem(
                    conversation=conversation,
                    message_count=4,
                    last_activity_at=created_at,
                )
            ],
            total=51,
        )
    )
    activity_from = datetime(2026, 11, 1, tzinfo=timezone.utc)
    activity_to = datetime(2026, 12, 1, tzinfo=timezone.utc)

    page = _service(repository).list_application_conversations(
        ListApplicationConversationsQuery(
            application_id=APPLICATION_ID,
            is_active=False,
            activity_from=activity_from,
            activity_to=activity_to,
            search="  visitor  ",
            sort_by="created",
            sort_order="asc",
            limit=10,
            offset=20,
        )
    )

    assert repository.query == {
        "application_id": APPLICATION_ID,
        "is_active": False,
        "activity_from": activity_from,
        "activity_to": activity_to,
        "search": "visitor",
        "sort_by": "created",
        "sort_order": "asc",
        "limit": 10,
        "offset": 20,
    }
    assert page.total == 51
    assert page.items[0].conversation.id == "00000000-0000-0000-0000-000000000002"
    assert page.items[0].message_count == 4
    assert page.items[0].last_activity_at == created_at


def test_list_conversations_rejects_reversed_activity_range():
    service = _service(_ConversationRepository())
    with pytest.raises(ApplicationError) as error:
        service.list_application_conversations(
            ListApplicationConversationsQuery(
                application_id=APPLICATION_ID,
                activity_from=datetime(2026, 12, 1, tzinfo=timezone.utc),
                activity_to=datetime(2026, 11, 1, tzinfo=timezone.utc),
            )
        )

    assert error.value.code == "conversation_date_range_invalid"


def test_conversation_repository_builds_filtered_aggregated_page_queries():
    class _Session:
        def __init__(self):
            self.statements = []

        def execute(self, statement):
            compiled = statement.compile(dialect=postgresql.dialect())
            self.statements.append(compiled)
            if "select count(conversations.id)" in str(compiled).lower():
                return SimpleNamespace(scalar_one=lambda: 0)
            return SimpleNamespace(all=lambda: [])

    session = _Session()
    result = SqlAlchemyConversationRepository(session).list_by_application_id(
        application_id=APPLICATION_ID,
        is_active=False,
        activity_from=datetime(2026, 11, 1, tzinfo=timezone.utc),
        activity_to=datetime(2026, 12, 1, tzinfo=timezone.utc),
        search="visitor",
        sort_by="activity",
        sort_order="desc",
        limit=10,
        offset=20,
    )

    page_sql = str(session.statements[1]).lower()
    assert result.total == 0
    assert result.items == []
    assert "conversations.application_id" in page_sql
    assert "conversations.is_active" in page_sql
    assert "max(messages.created_at)" in page_sql
    assert "messages.conversation_id" in page_sql
    assert session.statements[1].params["param_1"] == 10
    assert session.statements[1].params["param_2"] == 20


def test_conversation_list_route_returns_paginated_items_and_query_scope():
    captured = {}
    created_at = datetime(2026, 11, 1, tzinfo=timezone.utc)
    conversation = Conversation(
        id="00000000-0000-0000-0000-000000000002",
        application_id=APPLICATION_ID,
        conversation_identity="visitor-123",
        title="Pricing",
        summary=None,
        is_active=True,
        created_at=created_at,
        updated_at=created_at,
    )

    class _Service:
        def list_application_conversations(self, *, query):
            captured["query"] = query
            return SimpleNamespace(
                items=[
                    SimpleNamespace(
                        conversation=conversation,
                        message_count=4,
                        last_activity_at=created_at,
                    )
                ],
                total=26,
            )

    response = list_application_conversations(
        application_id=APPLICATION_ID,
        status_filter="active",
        activity_from=created_at,
        activity_to=datetime(2026, 12, 1, tzinfo=timezone.utc),
        search="visitor",
        sort_by="activity",
        sort_order="desc",
        limit=25,
        offset=25,
        service=_Service(),
    )

    assert captured["query"].application_id == APPLICATION_ID
    assert captured["query"].is_active is True
    assert captured["query"].search == "visitor"
    assert response.total == 26
    assert response.offset == 25
    assert response.items[0].message_count == 4
