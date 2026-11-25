from __future__ import annotations

from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)

from app.api.dependencies import (
    get_chat_application_service,
    get_platform_llm_provider,
)
from app.api.schemas.chat import (
    ChatActionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
    CitationResponse,
)
from app.modules.question_answering.application.commands import (
    AskChatQuestionCommand,
)
from app.modules.question_answering.application.services import (
    ChatApplicationService,
)
from app.modules.security.domain.entities import (
    ClientApplicationContext,
)
from app.api.client.dependencies import (
    get_client_application_context,
    get_optional_client_application_context,
    get_widget_application_id,
)

router = APIRouter(
    prefix="/client/chat",
    tags=["Client Chat"],
)


@router.post(
    "/preview/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
def create_customer_preview_message(
    request: ChatMessageRequest,
    http_request: Request,
    application_context: ClientApplicationContext | None = Depends(
        get_optional_client_application_context
    ),
    service: ChatApplicationService = Depends(get_chat_application_service),
    platform_llm_provider=Depends(get_platform_llm_provider),
) -> ChatMessageResponse:
    if application_context is not None:
        result = service.ask(
            AskChatQuestionCommand(
                application_id=str(application_context.application_id),
                conversation_identity=request.conversation_identity,
                message_text=request.message,
                conversation_title=request.conversation_title,
                top_k=request.top_k,
                request_id=getattr(http_request.state, "request_id", None),
                persist_conversation=False,
                conversation_messages=[
                    item.model_dump() for item in request.conversation_messages
                ],
            )
        )
        citations = [
            CitationResponse(
                document_id=item.document_id,
                title=item.document_title,
                chunk_id=item.chunk_id,
                source_uri=item.source_uri,
            )
            for item in result.citations
        ]
        return ChatMessageResponse(
            conversation_id=str(result.conversation_id),
            application_id=str(application_context.application_id),
            answer=result.answer_text,
            citations=citations,
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

    generation = platform_llm_provider.generate(
        system_prompt="You are a helpful customer-facing assistant. Answer clearly and directly.",
        user_prompt=request.message,
        temperature=0.2,
    )
    return ChatMessageResponse(
        conversation_id="",
        application_id=None,
        answer=generation.text,
        citations=[],
        actions=[],
        created_at=datetime.now(timezone.utc),
    )


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
def create_chat_message(
    request: ChatMessageRequest,
    http_request: Request,
    application_context: ClientApplicationContext = Depends(
        get_client_application_context,
    ),
    service: ChatApplicationService = Depends(
        get_chat_application_service,
    ),
) -> ChatMessageResponse:
    if not application_context.application_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid application context.",
        )

    if request.application_id and request.application_id != str(
        application_context.application_id
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
            application_id=str(
                application_context.application_id,
            ),
            conversation_identity=(request.conversation_identity),
            message_text=request.message,
            conversation_title=(request.conversation_title),
            top_k=request.top_k,
            request_id=getattr(http_request.state, "request_id", None),
        )
    )

    citations = [
        CitationResponse(
            document_id=item.document_id,
            title=item.document_title,
            chunk_id=item.chunk_id,
            source_uri=item.source_uri,
        )
        for item in result.citations
    ]

    return ChatMessageResponse(
        conversation_id=(
            str(result.conversation_id) if result.conversation_id is not None else ""
        ),
        application_id=str(application_context.application_id),
        answer=result.answer_text,
        citations=citations,
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


@router.post(
    "/widget/messages",
    response_model=ChatMessageResponse,
    status_code=status.HTTP_200_OK,
)
def create_widget_chat_message(
    request: ChatMessageRequest,
    http_request: Request,
    application_id: str = Depends(
        get_widget_application_id,
    ),
    service: ChatApplicationService = Depends(
        get_chat_application_service,
    ),
) -> ChatMessageResponse:
    result = service.ask(
        AskChatQuestionCommand(
            application_id=application_id,
            conversation_identity=(request.conversation_identity),
            message_text=request.message,
            conversation_title=(request.conversation_title),
            top_k=request.top_k,
            request_id=getattr(http_request.state, "request_id", None),
        )
    )

    citations = [
        CitationResponse(
            document_id=item.document_id,
            title=item.document_title,
            chunk_id=item.chunk_id,
            source_uri=item.source_uri,
        )
        for item in result.citations
    ]

    return ChatMessageResponse(
        conversation_id=(
            str(result.conversation_id) if result.conversation_id is not None else ""
        ),
        application_id=application_id,
        answer=result.answer_text,
        citations=citations,
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
