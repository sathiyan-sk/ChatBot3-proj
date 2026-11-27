from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from app.api.dependencies import (
    get_conversation_application_service,
    require_admin,
)
from app.api.schemas.conversations import (
    AppendMessageRequest,
    MessageResponse,
)
from app.modules.conversations.application.commands import (
    AppendMessageCommand,
)
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)


router = APIRouter(
    prefix="/admin/conversations",
    tags=["Admin Conversation Debug"],
)


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
    "/application/{application_id}/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[
        Depends(require_admin),
    ],
)
def append_admin_conversation_message(
    application_id: str,
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
            application_id=application_id,
        )
    )

    return MessageResponse.model_validate(
        _message_response_payload(result),
    )