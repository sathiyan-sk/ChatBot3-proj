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
)
from app.api.schemas.chat import (
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
    get_widget_application_id,
)

router = APIRouter(
    prefix="/client/chat",
    tags=["Client Chat"],
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

    result = service.ask(
        AskChatQuestionCommand(
            application_id=str(
                application_context.application_id,
            ),
            conversation_identity=(
                request.conversation_identity
            ),
            message_text=request.message,
            conversation_title=(
                request.conversation_title
            ),
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
        str(result.conversation_id)
        if result.conversation_id is not None
        else ""
    ),
    answer=result.answer_text,
    citations=citations,
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
            conversation_identity=(
                request.conversation_identity
            ),
            message_text=request.message,
            conversation_title=(
                request.conversation_title
            ),
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
            str(result.conversation_id)
            if result.conversation_id is not None
            else ""
        ),
        answer=result.answer_text,
        citations=citations,
        created_at=datetime.now(timezone.utc),
    )