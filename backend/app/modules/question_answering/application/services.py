from __future__ import annotations

import json
from dataclasses import dataclass
from collections.abc import Callable
from uuid import uuid4

from app.core.exceptions import ApplicationError
from app.knowledge_engine.pipelines.question_answering_pipeline import (
    QuestionAnsweringPipeline,
)
from app.knowledge_engine.shared.models import QuestionAnsweringPipelineRequest
from app.modules.question_answering.application.commands import AskChatQuestionCommand
from app.modules.question_answering.application.dto import AskChatQuestionResultDto
from app.modules.question_answering.application.dto import ChatActionDto
from app.modules.question_answering.contracts.response_models import CitationItem
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
    ResolveConversationCommand,
)
from app.modules.conversations.application.queries import GetConversationDetailQuery
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.documents.domain.repository_interfaces import (
    DocumentRepositoryInterface,
)
from app.modules.knowledge_bases.domain.repository_interfaces import (
    KnowledgeBaseRepositoryInterface,
)
from app.modules.settings.domain.repository_interfaces import (
    SettingsRepositoryInterface,
)
from app.modules.settings.domain.entities import PlatformSettings
from app.modules.leads.domain.policies import (
    LEAD_CONSENT_TEXT,
    LEAD_CONSENT_TEXT_VERSION,
    has_contact_intent,
)


@dataclass(slots=True)
class ChatApplicationService:
    knowledge_base_repository: KnowledgeBaseRepositoryInterface
    document_repository: DocumentRepositoryInterface
    settings_repository: SettingsRepositoryInterface
    conversation_service: ConversationApplicationService
    question_answering_pipeline_factory: Callable[
        [PlatformSettings | None],
        QuestionAnsweringPipeline,
    ]

    def ask(self, command: AskChatQuestionCommand) -> AskChatQuestionResultDto:
        message_text = command.message_text.strip()
        if not message_text:
            raise ApplicationError(
                message="Question text is required.",
                code="question_text_required",
                status_code=400,
            )

        application_settings = self.settings_repository.get_by_application_id(
            command.application_id
        )
        contact_intent = has_contact_intent(message_text)

        knowledge_base = None
        if not contact_intent:
            knowledge_base = self.knowledge_base_repository.get_by_application_id(
                command.application_id
            )
            if knowledge_base is None:
                raise ApplicationError(
                    message="Knowledge base not found for application.",
                    code="knowledge_base_not_found",
                    status_code=404,
                )

            ready_documents = [
                item
                for item in self.document_repository.list_by_knowledge_base_id(
                    knowledge_base_id=knowledge_base.id
                )
                if item.ready_version is not None
                and item.status in {"ready", "processing", "failed"}
            ]
            if not ready_documents:
                raise ApplicationError(
                    message=(
                        "No ready documents are available for question answering yet. "
                        "Upload or ingest content, then wait for the index to finish processing."
                    ),
                    code="knowledge_base_has_no_ready_documents",
                    status_code=409,
                )

        conversation_id = str(uuid4())
        conversation_messages = list(command.conversation_messages)
        user_message_id = ""
        if command.persist_conversation:
            conversation = self.conversation_service.resolve_conversation(
                ResolveConversationCommand(
                    application_id=command.application_id,
                    conversation_identity=command.conversation_identity,
                    title=command.conversation_title,
                    inactivity_timeout_minutes=(
                        None
                        if command.preserve_conversation
                        else (
                            application_settings.inactivity_timeout_minutes
                            if application_settings is not None
                            else 30
                        )
                    ),
                )
            )
            conversation_id = str(conversation.id)
            user_message = self.conversation_service.append_message(
                AppendMessageCommand(
                    conversation_id=conversation_id,
                    role="user",
                    content=message_text,
                )
            )
            user_message_id = str(user_message.id)
        else:
            conversation_messages.append(
                {"role": "user", "content": message_text}
            )

        if contact_intent:
            answer_text = (
                "I can help you send an enquiry to the business team. "
                "Use the contact form below to share your details and confirm "
                "that you agree to be contacted."
            )
            assistant_message_id = ""
            if command.persist_conversation:
                assistant_message = self.conversation_service.append_message(
                    AppendMessageCommand(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=answer_text,
                    )
                )
                assistant_message_id = str(assistant_message.id)
            return AskChatQuestionResultDto(
                conversation_id=conversation_id if command.persist_conversation else "",
                user_message_id=user_message_id,
                assistant_message_id=assistant_message_id,
                answer_text=answer_text,
                citations=[],
                actions=[
                    ChatActionDto(
                        type="contact_enquiry",
                        label="Submit an enquiry",
                        consent_text=LEAD_CONSENT_TEXT,
                        consent_text_version=LEAD_CONSENT_TEXT_VERSION,
                    )
                ],
            )

        if command.persist_conversation:
            conversation_detail = self.conversation_service.get_conversation_detail(
                GetConversationDetailQuery(
                    conversation_id=conversation_id,
                    application_id=command.application_id,
                )
            )
            conversation_messages = [
                {"role": item.role, "content": item.content}
                for item in conversation_detail.messages
            ]

        question_answering_pipeline = self.question_answering_pipeline_factory(
            application_settings
        )
        pipeline_result = question_answering_pipeline.run(
            QuestionAnsweringPipelineRequest(
                application_id=command.application_id,
                knowledge_base_id=knowledge_base.id,
                query_text=message_text,
                conversation_id=conversation_id,
                messages=conversation_messages,
                top_k=command.top_k,
                max_context_messages=(
                    application_settings.max_context_messages
                    if application_settings is not None
                    else 12
                ),
                llm_temperature=(
                    float(application_settings.llm_temperature)
                    if application_settings is not None
                    else None
                ),
                prompt_system_template=(
                    application_settings.prompt_system_template
                    if application_settings is not None
                    else None
                ),
                request_id=command.request_id,
            )
        )

        assistant_message_id = ""
        if command.persist_conversation:
            assistant_message = self.conversation_service.append_message(
                AppendMessageCommand(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=pipeline_result.answer_text,
                    citation_payload=json.dumps(
                        [
                            {
                                "document_id": str(item.document_id),
                                "document_title": str(item.document_title),
                                "chunk_id": str(item.chunk_id),
                                "source_uri": (
                                    str(item.source_uri)
                                    if item.source_uri is not None
                                    else None
                                ),
                            }
                            for item in pipeline_result.citations
                        ]
                    ),
                )
            )
            assistant_message_id = str(assistant_message.id)

        return AskChatQuestionResultDto(
            conversation_id=conversation_id if command.persist_conversation else "",
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            answer_text=pipeline_result.answer_text,
            citations=[
                CitationItem(
                    document_id=str(item.document_id),
                    document_title=str(item.document_title),
                    chunk_id=str(item.chunk_id),
                    source_uri=(
                        str(item.source_uri) if item.source_uri is not None else None
                    ),
                )
                for item in pipeline_result.citations
            ],
            actions=[],
        )
