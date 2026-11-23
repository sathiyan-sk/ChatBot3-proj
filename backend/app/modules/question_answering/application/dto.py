from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.question_answering.contracts.response_models import CitationItem


@dataclass(slots=True, frozen=True)
class ChatActionDto:
    type: str
    label: str
    consent_text: str
    consent_text_version: str


@dataclass(slots=True, frozen=True)
class AskChatQuestionResultDto:
    conversation_id: str
    user_message_id: str
    assistant_message_id: str
    answer_text: str
    citations: list[CitationItem]
    actions: list[ChatActionDto] = field(default_factory=list)