from __future__ import annotations

from fastapi import (
    APIRouter,
    Depends,
    Header,
    Response,
    status,
)

from app.api.client.dependencies import get_widget_application_id
from app.api.dependencies import (
    get_widget_application_service,
)
from app.api.schemas.widgets import (
    PublicWidgetConfigurationResponse,
)
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