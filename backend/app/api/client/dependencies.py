from __future__ import annotations

from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy import select

from app.api.dependencies import get_container
from app.composition import ApplicationContainer
from app.infrastructure.db.models.application_model import (
    ApplicationModel,
)
from app.infrastructure.security.origin_validator import (
    OriginValidator,
)
from app.modules.security.application.services import (
    ClientSecurityServices,
)
from app.modules.security.domain.entities import (
    ClientApplicationContext,
)
from app.modules.security.infrastructure.repositories import (
    ClientSecuritySqlAlchemyRepository,
)
from app.modules.widgets.infrastructure.repositories import (
    SqlAlchemyWidgetRepository,
)


def get_client_application_context(
    x_api_key: str = Header(
        default="",
        alias="X-API-Key",
    ),
    container: ApplicationContainer = Depends(
        get_container,
    ),
) -> ClientApplicationContext:
    normalized_api_key = x_api_key.strip()

    if not normalized_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key header is required.",
        )

    session = container.session_factory()

    try:
        security_service = ClientSecurityServices(
            client_security_repository=(
                ClientSecuritySqlAlchemyRepository(
                    session=session,
                )
            ),
        )

        return (
            security_service.resolve_application_context(
                normalized_api_key,
            )
        )

    finally:
        session.close()

def get_widget_application_id(
    request: Request,
    x_widget_key: str = Header(
        default="",
        alias="X-Widget-Key",
    ),
    origin: str | None = Header(
        default=None,
        alias="Origin",
    ),
    validator: OriginValidator = Depends(),
    container: ApplicationContainer = Depends(
        get_container,
    ),
) -> str:
    normalized_key = x_widget_key.strip()

    if not normalized_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Widget key is required.",
        )

    session = container.session_factory()

    try:
        repository = SqlAlchemyWidgetRepository(
            session=session,
        )

        widget = repository.get_by_public_key(
            normalized_key,
        )

        if widget is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid widget key.",
            )

        if not widget.is_enabled:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Widget is disabled.",
            )

        application = session.execute(
            select(ApplicationModel).where(
                ApplicationModel.id == str(widget.application_id),
            )
        ).scalar_one_or_none()

        if application is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Widget application not found.",
            )

        allowed_origins = application.allowed_origins or []
        # Resolve origin from Origin header or Referer fallback.
        request_origin = origin

        if not request_origin:
            referer = request.headers.get("referer")

            if referer:
                try:
                    parsed = urlsplit(referer)

                    if (
                        parsed.scheme in {"http", "https"}
                        and parsed.hostname
                        and parsed.username is None
                        and parsed.password is None
                        and (parsed.port is None or 0 < parsed.port <= 65535)
                    ):
                        request_origin = (
                            f"{parsed.scheme}://{parsed.netloc}"
                        )
                except ValueError:
                    request_origin = None

        # Reject requests without a valid origin.
        if not request_origin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin or valid Referer header is required.",
            )

        # Validate against the application's registered origins.
        if not validator.is_allowed(request_origin, allowed_origins):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Origin is not allowed for this application.",
            )
            
        return str(widget.application_id)

    finally:
        session.close()