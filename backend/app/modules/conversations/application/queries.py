from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class GetConversationDetailQuery:
    conversation_id: str
    application_id: str | None = None


@dataclass(slots=True, frozen=True)
class ListApplicationConversationsQuery:
    application_id: str
    is_active: bool | None = None
    activity_from: datetime | None = None
    activity_to: datetime | None = None
    search: str | None = None
    sort_by: str = "activity"
    sort_order: str = "desc"
    limit: int = 25
    offset: int = 0


@dataclass(slots=True, frozen=True)
class ListIdentityConversationsQuery:
    application_id: str
    conversation_identity: str