from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True, frozen=True)
class AskChatQuestionCommand:
    application_id: str
    conversation_identity: str
    message_text: str
    conversation_title: str | None = None
    top_k: int = 5
    request_id: str | None = None
    persist_conversation: bool = True
    preserve_conversation: bool = False
    conversation_messages: list[dict[str, str]] = field(default_factory=list)