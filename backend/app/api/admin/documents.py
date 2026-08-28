from __future__ import annotations

from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)

from app.api.admin.ingestion import run_document_ingestion_task
from app.api.dependencies import (
    get_document_application_service,
    get_settings,
    require_admin,
)
from app.api.schemas.documents import (
    CreateDocumentRequest,
    DocumentResponse,
    MarkDocumentFailedRequest,
    UpdateDocumentRequest,
)
from app.config.settings import Settings
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.modules.documents.application.commands import (
    ArchiveDocumentCommand,
    CreateDocumentCommand,
    DeleteDocumentCommand,
    MarkDocumentFailedCommand,
    MarkDocumentProcessingCommand,
    MarkDocumentReadyCommand,
    UpdateDocumentCommand,
)
from app.modules.documents.application.queries import (
    GetDocumentByIdQuery,
    ListDocumentsByKnowledgeBaseQuery,
    ListDocumentsByStatusQuery,
)
from app.modules.documents.application.services import (
    DocumentApplicationService,
)


router = APIRouter(
    prefix="/admin/documents",
    tags=["Admin Documents"],
    dependencies=[
        Depends(require_admin),
    ],
)


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_document(
    background_tasks: BackgroundTasks,
    knowledge_base_id: UUID = Form(...),
    title: str = Form(...),
    description: str | None = Form(None),
    file: UploadFile = File(...),
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    content = file.file.read()

    result = service.upload(
        knowledge_base_id=(knowledge_base_id),
        title=title,
        description=description,
        filename=file.filename or "uploaded-file",
        content_type=file.content_type,
        content=content,
    )

    background_tasks.add_task(
        run_document_ingestion_task,
        document_id=str(result.id),
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_document(
    request: CreateDocumentRequest,
    background_tasks: BackgroundTasks,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.create(
        CreateDocumentCommand(
            knowledge_base_id=str(request.knowledge_base_id),
            title=request.title,
            description=request.description,
            source_type=request.source_type,
            source_uri=request.source_uri or "",
        )
    )

    background_tasks.add_task(
        run_document_ingestion_task,
        document_id=str(result.id),
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
def get_document_by_id(
    document_id: UUID,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.get_by_id(
        GetDocumentByIdQuery(
            document_id=str(document_id),
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    knowledge_base_id: UUID | None = Query(None),
    status_value: str | None = Query(None, alias="status"),
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> list[DocumentResponse]:
    if knowledge_base_id is not None:
        results = service.list_by_knowledge_base(
            ListDocumentsByKnowledgeBaseQuery(
                knowledge_base_id=str(knowledge_base_id),
                status=status_value,
            )
        )

    elif status_value is not None:
        results = service.list_by_status(
            ListDocumentsByStatusQuery(
                status=status_value,
            )
        )

    else:
        results = service.list_all()

    return [
        DocumentResponse.model_validate(
            item,
            from_attributes=True,
        )
        for item in results
    ]


@router.put(
    "/{document_id}",
    response_model=DocumentResponse,
)
def update_document(
    document_id: UUID,
    request: UpdateDocumentRequest,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.update(
        UpdateDocumentCommand(
            document_id=str(document_id),
            title=request.title,
            description=request.description,
            status=request.status,
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.post(
    "/{document_id}/processing",
    response_model=DocumentResponse,
)
def mark_document_processing(
    document_id: UUID,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.mark_processing(
        MarkDocumentProcessingCommand(
            document_id=str(document_id),
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.post(
    "/{document_id}/ready",
    response_model=DocumentResponse,
)
def mark_document_ready(
    document_id: UUID,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.mark_ready(
        MarkDocumentReadyCommand(
            document_id=str(document_id),
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.post(
    "/{document_id}/failed",
    response_model=DocumentResponse,
)
def mark_document_failed(
    document_id: UUID,
    request: MarkDocumentFailedRequest,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.mark_failed(
        MarkDocumentFailedCommand(
            document_id=str(document_id),
            failure_reason=request.failure_reason,
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.post(
    "/{document_id}/archive",
    response_model=DocumentResponse,
)
def archive_document(
    document_id: UUID,
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> DocumentResponse:
    result = service.archive(
        ArchiveDocumentCommand(
            document_id=str(document_id),
        )
    )

    return DocumentResponse.model_validate(
        result,
        from_attributes=True,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
def delete_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    request: Request,
    settings: Settings = Depends(get_settings),
    service: DocumentApplicationService = Depends(
        get_document_application_service,
    ),
) -> Response:
    # Un-index vectors in the background (best-effort) so the delete
    # request stays fast even for large documents. Reuses the app-wide
    # session factory (no new engine per request).
    session_factory = request.app.state.session_factory

    def _cleanup_vectors() -> None:
        session = session_factory()
        try:
            vector_provider = PgVectorProvider(
                settings=settings,
                session=session,
            )
            vector_provider.delete_document_chunks(
                document_id=str(document_id),
            )
            session.commit()
        except Exception as e:
            session.rollback()
            # Consider logging: logger.error(f"Vector cleanup failed: {e}")
        finally:
            session.close()

    background_tasks.add_task(_cleanup_vectors)

    deleted = service.delete(
        DeleteDocumentCommand(
            document_id=str(document_id),
        ),
    )

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
