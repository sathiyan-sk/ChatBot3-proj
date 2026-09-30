from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Request,
    Response,
    status,
)

from app.api.client.dependencies import get_widget_application_id
from app.api.dependencies import (
    get_conversation_application_service,
    get_settings_application_service,
    get_widget_application_service,
)
from app.api.schemas.widgets import (
    PublicWidgetConfigurationResponse,
    WidgetSessionMessage,
    WidgetSessionRequest,
    WidgetSessionResponse,
)
from app.modules.conversations.application.commands import ResolveConversationCommand
from app.modules.conversations.application.queries import (
    GetConversationDetailQuery,
    ListIdentityConversationsQuery,
)
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.settings.application.services import SettingsApplicationService
from app.modules.widgets.application.services import (
    WidgetApplicationService,
)


router = APIRouter(
    prefix="/client/widget",
    tags=["Client Widget"],
)


@router.get(
    "/configuration",
    response_model=PublicWidgetConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
def get_widget_configuration(
    response: Response,
    x_widget_key: str | None = Header(
        default=None,
        alias="X-Widget-Key",
    ),
    _: str = Depends(get_widget_application_id),
    service: WidgetApplicationService = Depends(
        get_widget_application_service,
    ),
) -> PublicWidgetConfigurationResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    configuration = (
        service.get_public_configuration(
            x_widget_key or "",
        )
    )

    return PublicWidgetConfigurationResponse(
        **configuration,
    )


@router.post(
    "/session",
    response_model=WidgetSessionResponse,
    status_code=status.HTTP_200_OK,
)
def start_widget_session(
    payload: WidgetSessionRequest,
    request: Request,
    response: Response,
    application_id: str = Depends(get_widget_application_id),
    conversation_service: ConversationApplicationService = Depends(
        get_conversation_application_service,
    ),
    settings_service: SettingsApplicationService = Depends(
        get_settings_application_service,
    ),
) -> WidgetSessionResponse:
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    application_settings = settings_service.settings_repository.get_by_application_id(
        application_id
    )
    conversation_service.cleanup_expired_conversations(
        default_retention_days=request.app.state.settings.chat_history_retention_days,
        application_id=application_id,
    )
    active_conversation = conversation_service.resolve_conversation(
        ResolveConversationCommand(
            application_id=application_id,
            conversation_identity=payload.conversation_identity,
            title="Website chat",
            inactivity_timeout_minutes=(
                application_settings.inactivity_timeout_minutes
                if application_settings is not None
                else 30
            ),
        )
    )

    visitor_conversations = conversation_service.list_identity_conversations(
        ListIdentityConversationsQuery(
            application_id=application_id,
            conversation_identity=payload.conversation_identity,
        )
    )
    history: list[WidgetSessionMessage] = []
    for conversation in reversed(visitor_conversations):
        detail = conversation_service.get_conversation_detail(
            GetConversationDetailQuery(
                conversation_id=conversation.id,
                application_id=application_id,
            )
        )
        history.extend(
            WidgetSessionMessage(
                role=message.role,
                content=message.content,
                created_at=message.created_at,
            )
            for message in detail.messages
        )

    return WidgetSessionResponse(
        conversation_id=str(active_conversation.id),
        messages=history,
    )