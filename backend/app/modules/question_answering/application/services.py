from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.exceptions import ApplicationError
from app.knowledge_engine.pipelines.question_answering_pipeline import QuestionAnsweringPipeline
from app.knowledge_engine.shared.models import QuestionAnsweringPipelineRequest
from app.modules.question_answering.application.commands import AskChatQuestionCommand
from app.modules.question_answering.application.dto import AskChatQuestionResultDto
from app.modules.question_answering.contracts.response_models import CitationItem
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
    ResolveConversationCommand,
)
from app.modules.conversations.application.queries import GetConversationDetailQuery
from app.modules.conversations.application.services import ConversationApplicationService
from app.modules.documents.domain.repository_interfaces import DocumentRepositoryInterface
from app.modules.knowledge_bases.domain.repository_interfaces import KnowledgeBaseRepositoryInterface


@dataclass(slots=True)
class ChatApplicationService:
    knowledge_base_repository: KnowledgeBaseRepositoryInterface
    document_repository: DocumentRepositoryInterface
    conversation_service: ConversationApplicationService
    question_answering_pipeline: QuestionAnsweringPipeline

    def ask(self, command: AskChatQuestionCommand) -> AskChatQuestionResultDto:
        message_text = command.message_text.strip()
        if not message_text:
            raise ApplicationError(
                message="Question text is required.",
                code="question_text_required",
                status_code=400,
            )

        knowledge_base = self.knowledge_base_repository.get_by_application_id(command.application_id)
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
            if item.status == "ready"
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

        conversation = self.conversation_service.resolve_conversation(
            ResolveConversationCommand(
                application_id=command.application_id,
                conversation_identity=command.conversation_identity,
                title=command.conversation_title,
            )
        )

        user_message = self.conversation_service.append_message(
            AppendMessageCommand(
                conversation_id=conversation.id,
                role="user",
                content=message_text,
            )
        )

        conversation_detail = (
    self.conversation_service.get_conversation_detail(
        GetConversationDetailQuery(
            conversation_id=str(
                conversation.id,
            ),
            application_id=str(
                command.application_id,
            ),
        )
    )
)

        pipeline_result = self.question_answering_pipeline.run(
            QuestionAnsweringPipelineRequest(
                application_id=command.application_id,
                knowledge_base_id=knowledge_base.id,
                query_text=message_text,
                conversation_id=conversation.id,
                messages=[
                    {"role": item.role, "content": item.content}
                    for item in conversation_detail.messages
                ],
            )
        )

        assistant_message = self.conversation_service.append_message(
            AppendMessageCommand(
                conversation_id=conversation.id,
                role="assistant",
                content=pipeline_result.answer_text,
                citation_payload=json.dumps(
    [
        {
            "document_id": str(item.document_id),
            "document_title": str(
                item.document_title
            ),
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

        return AskChatQuestionResultDto(
            conversation_id=str(conversation.id),
            user_message_id=str(user_message.id),
            assistant_message_id=str(assistant_message.id),
            answer_text=pipeline_result.answer_text,
            citations=[
    CitationItem(
        document_id=str(item.document_id),
        document_title=str(
            item.document_title
        ),
        chunk_id=str(item.chunk_id),
        source_uri=(
            str(item.source_uri)
            if item.source_uri is not None
            else None
        ),
    )
    for item in pipeline_result.citations
],
        )