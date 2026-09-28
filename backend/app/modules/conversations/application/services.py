from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.exceptions import ApplicationError
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
    ResolveConversationCommand,
    UpdateConversationCommand,
)
from app.modules.conversations.application.dto import (
    ConversationDetailDto,
    ConversationDto,
    MessageDto,
)
from app.modules.conversations.application.queries import (
    GetConversationDetailQuery,
    ListApplicationConversationsQuery,
    ListIdentityConversationsQuery,
)
from app.modules.conversations.domain.entities import Conversation, Message
from app.modules.conversations.domain.policies import (
    normalize_message_content,
    normalize_summary,
    normalize_title,
)
from app.modules.conversations.domain.repository_interfaces import (
    ConversationRepositoryInterface,
    MessageRepositoryInterface,
)
from app.modules.conversations.domain.value_objects import ConversationIdentity, MessageRole


@dataclass(slots=True)
class ConversationApplicationService:
    conversation_repository: ConversationRepositoryInterface
    message_repository: MessageRepositoryInterface

    def cleanup_expired_conversations(
        self,
        *,
        default_retention_days: int,
        application_id: str | None = None,
    ) -> int:
        return self.conversation_repository.delete_expired_conversations(
            default_retention_days=default_retention_days,
            application_id=application_id,
        )

    def resolve_conversation(self, command: ResolveConversationCommand) -> ConversationDto:
        identity = ConversationIdentity(command.conversation_identity)

        existing_conversation = self.conversation_repository.get_active_by_identity(
            application_id=command.application_id,
            conversation_identity=identity.value,
        )
        if existing_conversation is not None:
            timeout = command.inactivity_timeout_minutes
            if timeout is None:
                return self._to_conversation_dto(existing_conversation)

            last_activity = existing_conversation.updated_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) - last_activity < timedelta(minutes=timeout):
                return self._to_conversation_dto(existing_conversation)

            self.conversation_repository.update(
                conversation_id=existing_conversation.id,
                title=existing_conversation.title,
                summary=existing_conversation.summary,
                is_active=False,
            )

        created_conversation = self.conversation_repository.create(
            application_id=command.application_id,
            conversation_identity=identity.value,
            title=normalize_title(command.title),
            summary=None,
            is_active=True,
        )
        return self._to_conversation_dto(created_conversation)

    def append_message(self, command: AppendMessageCommand) -> MessageDto:
        conversation = self.conversation_repository.get_by_id(command.conversation_id)
        if conversation is None:
            raise ApplicationError(
                message="Conversation not found.",
                code="conversation_not_found",
                status_code=404,
            )
        if not conversation.is_active:
            raise ApplicationError(
                message="Conversation is inactive.",
                code="conversation_inactive",
                status_code=409,
            )

        role = MessageRole(command.role)
        content = normalize_message_content(command.content)
        next_sequence_number = self.message_repository.get_latest_sequence_number(conversation.id) + 1

        created_message = self.message_repository.create(
            conversation_id=conversation.id,
            role=role.value,
            content=content,
            sequence_number=next_sequence_number,
            citation_payload=command.citation_payload,
        )
        self.conversation_repository.touch_activity(conversation.id)
        return self._to_message_dto(created_message)

    def get_conversation_detail(
    self,
    query: GetConversationDetailQuery,
    ) -> ConversationDetailDto:

        if query.application_id is None:
            conversation = (
                self.conversation_repository.get_by_id(
                query.conversation_id,
            )
        )
        else:
            conversation = (
                self.conversation_repository
                .get_by_id_and_application_id(
                conversation_id=query.conversation_id,
                application_id=query.application_id,
            )
        )

        if conversation is None:
            raise ApplicationError(
            message="Conversation not found.",
            code="conversation_not_found",
            status_code=404,
        )

        messages = (
            self.message_repository
            .list_by_conversation_id(
            conversation.id,
        )
    )

        return ConversationDetailDto(
        conversation=self._to_conversation_dto(
            conversation,
        ),
        messages=[
            self._to_message_dto(item)
            for item in messages
        ],
    )

    def list_application_conversations(
        self,
        query: ListApplicationConversationsQuery,
    ) -> list[ConversationDto]:
        conversations = self.conversation_repository.list_by_application_id(query.application_id)
        return [self._to_conversation_dto(item) for item in conversations]

    def list_identity_conversations(
        self,
        query: ListIdentityConversationsQuery,
    ) -> list[ConversationDto]:
        identity = ConversationIdentity(query.conversation_identity)
        conversations = self.conversation_repository.list_by_identity(
            application_id=query.application_id,
            conversation_identity=identity.value,
        )
        return [self._to_conversation_dto(item) for item in conversations]

    def update_conversation(self, command: UpdateConversationCommand) -> ConversationDto:
        conversation = self.conversation_repository.get_by_id(command.conversation_id)
        if conversation is None:
            raise ApplicationError(
                message="Conversation not found.",
                code="conversation_not_found",
                status_code=404,
            )

        updated_conversation = self.conversation_repository.update(
            conversation_id=conversation.id,
            title=normalize_title(command.title),
            summary=normalize_summary(command.summary),
            is_active=command.is_active,
        )
        return self._to_conversation_dto(updated_conversation)

    def _to_conversation_dto(self, conversation: Conversation) -> ConversationDto:
        return ConversationDto(
            id=conversation.id,
            application_id=conversation.application_id,
            conversation_identity=conversation.conversation_identity,
            title=conversation.title,
            summary=conversation.summary,
            is_active=conversation.is_active,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        )

    def _to_message_dto(self, message: Message) -> MessageDto:
        return MessageDto(
            id=message.id,
            conversation_id=message.conversation_id,
            role=message.role,
            content=message.content,
            sequence_number=message.sequence_number,
            citation_payload=message.citation_payload,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )