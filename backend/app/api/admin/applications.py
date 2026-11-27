from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.dependencies import get_container, clear_cors_cache
from app.api.schemas.applications import (
    ApplicationDeletionSummaryResponse,
    ApplicationResponse,
    CreateApplicationRequest,
    CreatedApplicationResponse,
    UpdateApplicationRequest,
)
from app.composition import ApplicationContainer
from app.infrastructure.providers.storage.supabase_storage_provider import (
    SupabaseStorageProvider,
)
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.modules.applications.application.commands import (
    CreateApplicationCommand,
    UpdateApplicationCommand,
)
from app.modules.applications.application.services import ApplicationServices
from app.modules.applications.application.deletion import (
    ApplicationDeletionService,
)
from app.modules.applications.infrastructure.repositories import (
    ApplicationProvisioningSqlAlchemyRepository,
    ApplicationSqlAlchemyRepository,
)


router = APIRouter(
    prefix="/admin/applications",
    tags=["Admin Applications"],
)


def _build_application_services(
    container: ApplicationContainer,
) -> tuple[Session, ApplicationServices]:
    session = container.session_factory()

    service = ApplicationServices(
        session=session,
        application_repository=ApplicationSqlAlchemyRepository(session),
        provisioning_repository=ApplicationProvisioningSqlAlchemyRepository(session),
        platform_settings=container.settings,
    )

    return session, service


def _build_application_deletion_service(
    container: ApplicationContainer,
) -> tuple[Session, ApplicationDeletionService]:
    session = container.session_factory()
    service = ApplicationDeletionService(
        session=session,
        storage_provider=SupabaseStorageProvider(
            settings=container.settings.storage,
        ),
        vector_provider=PgVectorProvider(
            settings=container.settings,
            session=session,
        ),
    )
    return session, service


def _application_response(application) -> ApplicationResponse:
    """
    Convert the slots-based ApplicationDto into the API response model.
    """

    return ApplicationResponse(
        id=str(application.id),
        name=application.name,
        slug=application.slug,
        description=application.description,
        client_type=application.client_type,
        allowed_origins=list(application.allowed_origins or []),
        is_active=application.is_active,
        created_at=application.created_at,
        updated_at=application.updated_at,
    )


@router.post(
    "",
    response_model=CreatedApplicationResponse,
    status_code=201,
)
def create_application(
    payload: CreateApplicationRequest,
    container: ApplicationContainer = Depends(get_container),
) -> CreatedApplicationResponse:
    session, service = _build_application_services(container)

    try:
        result = service.create_application(
            CreateApplicationCommand(
                name=payload.name,
                description=payload.description,
                client_type=payload.client_type,
                allowed_origins=payload.allowed_origins,
            )
        )

        return CreatedApplicationResponse(
            application=_application_response(result.application),
            api_key=result.api_key,
            api_key_prefix=result.api_key_prefix,
        )

    finally:
        session.close()


@router.get(
    "",
    response_model=list[ApplicationResponse],
)
def list_applications(
    container: ApplicationContainer = Depends(get_container),
) -> list[ApplicationResponse]:
    session, service = _build_application_services(container)

    try:
        results = service.list_applications()
        return [_application_response(item) for item in results]

    finally:
        session.close()


@router.get(
    "/{application_id}",
    response_model=ApplicationResponse,
)
def get_application(
    application_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> ApplicationResponse:
    session, service = _build_application_services(container)

    try:
        result = service.get_application(application_id)
        return _application_response(result)

    finally:
        session.close()


@router.put(
    "/{application_id}",
    response_model=ApplicationResponse,
)
def update_application(
    application_id: str,
    payload: UpdateApplicationRequest,
    request: Request,
    container: ApplicationContainer = Depends(get_container),
) -> ApplicationResponse:
    session, service = _build_application_services(container)

    try:
        result = service.update_application(
            UpdateApplicationCommand(
                application_id=application_id,
                name=payload.name,
                description=payload.description,
                client_type=payload.client_type,
                allowed_origins=payload.allowed_origins,
                is_active=payload.is_active,
            )
        )
        
        # Clear CORS cache for all widget keys since allowed_origins changed
        clear_cors_cache(request)

        return _application_response(result)

    finally:
        session.close()


@router.delete(
    "/{application_id}",
    status_code=204,
)
def permanently_delete_application(
    application_id: str,
    request: Request,
    container: ApplicationContainer = Depends(get_container),
) -> Response:
    session, service = _build_application_deletion_service(container)

    try:
        service.delete_permanently(application_id)
        return Response(status_code=204)

    finally:
        clear_cors_cache(request)
        session.close()


@router.get(
    "/{application_id}/deletion-summary",
    response_model=ApplicationDeletionSummaryResponse,
)
def get_application_deletion_summary(
    application_id: str,
    container: ApplicationContainer = Depends(get_container),
) -> ApplicationDeletionSummaryResponse:
    session, service = _build_application_deletion_service(container)

    try:
        return ApplicationDeletionSummaryResponse(
            **service.get_deletion_summary(application_id),
        )
    finally:
        session.close()


@router.post(
    "/{application_id}/deactivate",
    response_model=ApplicationResponse,
)
def deactivate_application(
    application_id: str,
    request: Request,
    container: ApplicationContainer = Depends(get_container),
) -> ApplicationResponse:
    session, service = _build_application_services(container)

    try:
        result = service.deactivate_application(application_id)
        clear_cors_cache(request)
        return _application_response(result)

    finally:
        session.close()