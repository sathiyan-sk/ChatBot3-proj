from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.client.dependencies import get_client_application_context
from app.api.dependencies import (
    get_chat_application_service,
    get_conversation_application_service,
    require_admin,
)
from app.api.schemas.chat import (
    ChatActionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    CitationResponse,
)
from app.api.schemas.conversations import (
    AppendMessageRequest,
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
    ResolveConversationRequest,
    UpdateConversationRequest,
)
from app.modules.question_answering.application.commands import (
    AskChatQuestionCommand,
)
from app.modules.question_answering.application.services import (
    ChatApplicationService,
)
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
    ResolveConversationCommand,
    UpdateConversationCommand,
)
from app.modules.conversations.application.queries import (
    GetConversationDetailQuery,
    ListApplicationConversationsQuery,
)
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.security.domain.entities import ClientApplicationContext


router = APIRouter(
    prefix="/admin/conversations",
    tags=["Admin Conversations"],
    dependencies=[
        Depends(require_admin),
    ],
)


def _conversation_response_payload(
    conversation: Any,
) -> dict[str, Any]:
    payload = asdict(conversation)

    payload["id"] = str(
        payload["id"],
    )

    payload["application_id"] = str(
        payload["application_id"],
    )

    return payload


def _message_response_payload(
    message: Any,
) -> dict[str, Any]:
    payload = asdict(message)

    payload["id"] = str(
        payload["id"],
    )

    payload["conversation_id"] = str(
        payload["conversation_id"],
    )

    return payload


@router.post(
    "/resolve",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def resolve_conversation(
    payload: ResolveConversationRequest,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> ConversationResponse:
    result = service.resolve_conversation(
        ResolveConversationCommand(
            application_id=payload.application_id,
            conversation_identity=(
                payload.conversation_identity
            ),
            title=payload.title,
        )
    )

    return ConversationResponse.model_validate(
        _conversation_response_payload(result),
    )


@router.get(
    "/application/{application_id}",
    response_model=list[ConversationResponse],
)
def list_application_conversations(
    application_id: str,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> list[ConversationResponse]:
    result = (
        service.list_application_conversations(
            query=ListApplicationConversationsQuery(
                application_id=application_id,
            ),
        )
    )

    return [
        ConversationResponse.model_validate(
            _conversation_response_payload(item),
        )
        for item in result
    ]


@router.post(
    "/application/{application_id}/sandbox/messages",
    response_model=ChatMessageResponse,
)
def create_application_sandbox_message(
    application_id: str,
    request: ChatMessageRequest,
    http_request: Request,
    application_context: ClientApplicationContext = Depends(
        get_client_application_context,
    ),
    service: ChatApplicationService = Depends(
        get_chat_application_service,
    ),
) -> ChatMessageResponse:
    if str(application_context.application_id) != application_id or (
        request.application_id
        and request.application_id != application_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "The API key does not belong to the selected application.",
                "code": "chat_application_key_mismatch",
            },
        )

    result = service.ask(
        AskChatQuestionCommand(
            application_id=application_id,
            conversation_identity=f"sandbox-{application_id}",
            message_text=request.message,
            conversation_title="Admin Sandbox Test",
            top_k=request.top_k,
            request_id=getattr(http_request.state, "request_id", None),
            preserve_conversation=True,
        )
    )
    return ChatMessageResponse(
        conversation_id=result.conversation_id,
        application_id=application_id,
        answer=result.answer_text,
        citations=[
            CitationResponse(
                document_id=item.document_id,
                title=item.document_title,
                chunk_id=item.chunk_id,
                source_uri=item.source_uri,
            )
            for item in result.citations
        ],
        actions=[
            ChatActionResponse(
                type=action.type,
                label=action.label,
                consent_text=action.consent_text,
                consent_text_version=action.consent_text_version,
            )
            for action in result.actions
        ],
        created_at=datetime.now(timezone.utc),
    )


@router.get(
    "/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def get_conversation_detail(
    conversation_id: str,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> ConversationDetailResponse:
    result = service.get_conversation_detail(
        GetConversationDetailQuery(
            conversation_id=conversation_id,
            application_id=None,
        )
    )

    return ConversationDetailResponse(
        conversation=ConversationResponse.model_validate(
            _conversation_response_payload(
                result.conversation,
            ),
        ),
        messages=[
            MessageResponse.model_validate(
                _message_response_payload(item),
            )
            for item in result.messages
        ],
    )


@router.put(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> ConversationResponse:
    result = service.update_conversation(
        UpdateConversationCommand(
            conversation_id=conversation_id,
            title=payload.title,
            summary=payload.summary,
            is_active=payload.is_active,
        )
    )

    return ConversationResponse.model_validate(
        _conversation_response_payload(result),
    )


@router.delete(
    "/{conversation_id}",
    response_model=ConversationResponse,
)
def close_conversation(
    conversation_id: str,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> ConversationResponse:
    result = service.update_conversation(
        UpdateConversationCommand(
            conversation_id=conversation_id,
            title=None,
            summary=None,
            is_active=False,
        )
    )

    return ConversationResponse.model_validate(
        _conversation_response_payload(result),
    )


@router.post(
    "/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def append_message(
    conversation_id: str,
    payload: AppendMessageRequest,
    service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
) -> MessageResponse:
    allowed_roles = {
        "user",
        "assistant",
        "system",
    }

    if payload.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Unsupported message role.",
                "code": "message_role_invalid",
            },
        )

    result = service.append_message(
        AppendMessageCommand(
            conversation_id=conversation_id,
            role=payload.role,
            content=payload.content,
            citation_payload=(
                payload.citation_payload
            ),
        )
    )

    return MessageResponse.model_validate(
        _message_response_payload(result),
    )