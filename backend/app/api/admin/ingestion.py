from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.api.dependencies import (
    get_document_application_service,
    get_knowledge_ingestion_pipeline,
    get_session,
)
from app.api.schemas.ingestion import (
    IngestionResponse,
    StartIngestionRequest,
)
from app.infrastructure.db.models.document_model import DocumentModel
from app.knowledge_engine.shared.models import (
    KnowledgeIngestionPipelineRequest,
)
from app.modules.documents.application.commands import (
    MarkDocumentFailedCommand,
    MarkDocumentProcessingCommand,
    MarkDocumentReadyCommand,
)
from app.modules.documents.application.queries import (
    GetDocumentByIdQuery,
)
from app.modules.documents.application.services import (
    DocumentApplicationService,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/admin/ingestion",
    tags=["Admin Ingestion"],
)
def _safe_rollback(session: Session) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        logger.exception(
            "Database rollback failed; closing broken session.",
        )

def _resolve_source_type(
    document: object,
    source_path: str,
) -> str:
    stored_source_type = getattr(
        document,
        "source_type",
        None,
    )

    if isinstance(
        stored_source_type,
        str,
    ):
        normalized_type = (
            stored_source_type.strip().lower()
        )

        if normalized_type in {
            "pdf",
            "website",
            "csv",
            "image",
            "doc",
            "docx",
            "txt",
            "text",
            "md",
            "markdown",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
        }:
            return normalized_type

    filename = source_path.rsplit(
        "/",
        1,
    )[-1]

    if "." not in filename:
        return "file"

    extension = (
        filename.rsplit(
            ".",
            1,
        )[-1]
        .strip()
        .lower()
    )

    extension_aliases = {
        "markdown": "md",
        "text": "txt",
        "jpeg": "image",
        "jpg": "image",
        "png": "image",
        "tiff": "image",
        "webp": "image",
        "htm": "website",
        "html": "website",
    }

    return extension_aliases.get(
        extension,
        extension or "file",
    )


def _validate_storage_path(
    document: object,
) -> str:
    source_path = getattr(
        document,
        "storage_path",
        None,
    )

    if not isinstance(
        source_path,
        str,
    ):
        raise ValueError(
            "Document storage path is missing."
        )

    normalized_path = source_path.strip()

    if not normalized_path:
        raise ValueError(
            "Document storage path is empty."
        )

    if normalized_path.lower() in {
        "null",
        "none",
        "string",
    }:
        raise ValueError(
            "Document storage path is invalid."
        )

    return normalized_path


def _build_pipeline_request(
    document: object,
    source_path: str,
    source_type: str,
) -> KnowledgeIngestionPipelineRequest:
    return KnowledgeIngestionPipelineRequest(
        document_id=str(getattr(document, "id", "")),
        knowledge_base_id=str(getattr(document, "knowledge_base_id", "")),
        source_type=source_type,
        source_path=source_path,
        source_identifier=source_path,
    )



def _resolve_source_identifier(
    document: object,
) -> str:
    source_type = getattr(
        document,
        "source_type",
        None,
    )

    normalized_source_type = (
        source_type.strip().lower()
        if isinstance(source_type, str)
        else ""
    )

    if normalized_source_type == "website":
        source_uri = getattr(
            document,
            "source_uri",
            None,
        )

        if not isinstance(
            source_uri,
            str,
        ):
            raise ValueError(
                "Website source URI is missing."
            )

        normalized_uri = source_uri.strip()

        if not normalized_uri:
            raise ValueError(
                "Website source URI is empty."
            )

        if not (
            normalized_uri.startswith(
                "http://"
            )
            or normalized_uri.startswith(
                "https://"
            )
        ):
            raise ValueError(
                "Website source URI must use "
                "http or https."
            )

        return normalized_uri

    return _validate_storage_path(
        document,
    )


def _get_app_session_factory(app: object):
    session_factory = getattr(app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError(
            "Application database session factory is not initialized.",
        )
    return session_factory


def claim_next_pending_document(
    session_factory,
    stale_after_minutes: int = 120,
) -> str | None:
    session: Session = session_factory()
    try:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=stale_after_minutes)
        document = session.execute(
            select(DocumentModel)
            .where(
                or_(
                    DocumentModel.status == "pending",
                    and_(
                        DocumentModel.status == "processing",
                        DocumentModel.updated_at < stale_before,
                    ),
                )
            )
            .order_by(DocumentModel.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if document is None:
            return None

        was_stale = document.status == "processing"
        document.status = "processing"
        document.failure_reason = None
        document.updated_at = datetime.now(timezone.utc)
        document_id = str(document.id)
        session.commit()
        logger.info(
            "Claimed document ingestion job",
            extra={"document_id": document_id, "reclaimed_stale_job": was_stale},
        )
        return document_id
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def run_document_ingestion_worker(
    session_factory,
    *,
    application: object,
    worker_id: int,
    stale_after_minutes: int = 120,
    poll_interval_seconds: float = 2.0,
    ingestion_timeout_seconds: int | None = None,
) -> None:
    logger.info("Document ingestion worker started", extra={"worker_id": worker_id})
    while True:
        try:
            document_id = await asyncio.to_thread(
                claim_next_pending_document,
                session_factory,
                stale_after_minutes,
            )
            if document_id is None:
                await asyncio.sleep(poll_interval_seconds)
                continue

            timeout_value = (
                ingestion_timeout_seconds
                if ingestion_timeout_seconds is not None
                else getattr(application.state.settings, "ingestion_timeout_seconds", 300)
            )

            task = asyncio.create_task(
                asyncio.to_thread(
                    _execute_document_ingestion_with_timeout,
                    document_id,
                    application,
                    timeout_seconds=timeout_value,
                )
            )
            while not task.done():
                try:
                    await asyncio.wait_for(
                        asyncio.shield(task),
                        timeout=30,
                    )
                except asyncio.TimeoutError:
                    try:
                        await asyncio.to_thread(
                            touch_document_ingestion_heartbeat,
                            session_factory,
                            document_id,
                        )
                    except Exception:
                        logger.exception(
                            "Could not update document ingestion heartbeat",
                            extra={"document_id": document_id},
                        )
            await task
        except asyncio.CancelledError:
            logger.info(
                "Document ingestion worker stopped",
                extra={"worker_id": worker_id},
            )
            raise
        except Exception:
            logger.exception(
                "Document ingestion worker iteration failed",
                extra={"worker_id": worker_id},
            )
            await asyncio.sleep(poll_interval_seconds)


def touch_document_ingestion_heartbeat(
    session_factory,
    document_id: str,
) -> None:
    session: Session = session_factory()
    try:
        session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.status == "processing",
            )
            .values(updated_at=datetime.now(timezone.utc))
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _mark_document_failed_and_log(
    session_factory,
    document_id: str,
    reason: str,
    settings: object,
) -> None:
    session: Session | None = None
    try:
        session = session_factory()
        service = get_document_application_service(
            request=SimpleNamespace(
                app=SimpleNamespace(
                    state=SimpleNamespace(
                        session_factory=session_factory,
                        settings=settings,
                    )
                )
            ),
            session=session,
        )
        service.mark_failed(
            MarkDocumentFailedCommand(
                document_id=document_id,
                failure_reason=reason,
            )
        )
        session.commit()
        logger.error(
            "Document ingestion failed and was marked failed",
            extra={
                "document_id": document_id,
                "failure_reason": reason,
            },
        )
    except Exception:
        if session is not None:
            _safe_rollback(session)
        logger.exception(
            "Could not mark document as failed after timeout",
            extra={"document_id": document_id},
        )
    finally:
        if session is not None:
            session.close()


def _run_document_ingestion_task_in_subprocess(
    document_id: str,
    queue: object | None = None,
) -> None:
    session_factory = None
    try:
        level_name = os.getenv("LOG_LEVEL", "INFO").upper()
        logging.basicConfig(
            level=getattr(logging, level_name, logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
            force=True,
        )

        from app.config.settings import get_settings
        from app.infrastructure.db.session import create_session_factory

        settings = get_settings()
        session_factory = create_session_factory(settings.database.url)
        application = SimpleNamespace(
            state=SimpleNamespace(
                settings=settings,
                session_factory=session_factory,
            )
        )
        run_document_ingestion_task(document_id, application)
        if queue is not None:
            queue.put(("success", None))
    except Exception as exc:
        if queue is not None:
            queue.put(("error", str(exc)))
        raise
    finally:
        if session_factory is not None:
            bind = getattr(session_factory, "kw", {}).get("bind")
            if bind is not None:
                bind.dispose()


def _execute_document_ingestion_with_timeout(
    document_id: str,
    application: object,
    *,
    timeout_seconds: int,
) -> None:
    if timeout_seconds <= 0:
        timeout_seconds = 300

    context = multiprocessing.get_context("spawn")
    queue_factory = getattr(context, "Queue", None) or multiprocessing.Queue
    queue = queue_factory()
    process = context.Process(
        target=_run_document_ingestion_task_in_subprocess,
        args=(document_id, queue),
    )
    process.start()
    process.join(timeout=timeout_seconds)

    if process.is_alive():
        logger.warning(
            "Document ingestion exceeded timeout; terminating worker process",
            extra={
                "document_id": document_id,
                "timeout_seconds": timeout_seconds,
            },
        )
        process.terminate()
        process.join(5)
        session_factory = getattr(application.state, "session_factory", None)
        if session_factory is not None:
            _mark_document_failed_and_log(
                session_factory,
                document_id,
                f"Document ingestion timed out after {timeout_seconds} seconds.",
                application.state.settings,
            )
        raise TimeoutError(
            f"Document ingestion timed out after {timeout_seconds} seconds."
        )

    if process.exitcode not in (0, None):
        session_factory = getattr(application.state, "session_factory", None)
        if session_factory is not None:
            _mark_document_failed_and_log(
                session_factory,
                document_id,
                f"Document ingestion process exited unexpectedly with code {process.exitcode}.",
                application.state.settings,
            )
        raise RuntimeError(
            f"Document ingestion process exited unexpectedly with code {process.exitcode}."
        )

    try:
        if not queue.empty():
            status, payload = queue.get_nowait()
            if status == "error":
                raise RuntimeError(payload or "document ingestion failed")
    except Exception:
        pass


def run_document_ingestion_task(
    document_id: str,
    application: object | None = None,
) -> None:
    from types import SimpleNamespace

    if application is None:
        from app.main import app as application

    request_context = SimpleNamespace(app=application)
    session_factory = None
    session: Session | None = None

    try:
        session_factory = _get_app_session_factory(application)
        session = session_factory()
        logger.info(
            "Document ingestion task started",
            extra={"document_id": document_id},
        )
        document_service = get_document_application_service(
            request=request_context,
            session=session,
        )

        document = document_service.get_by_id(
            GetDocumentByIdQuery(
                document_id=document_id,
            )
        )

        document_service.mark_processing(
            MarkDocumentProcessingCommand(
                document_id=document_id,
            )
        )
        session.commit()

        source_identifier = _resolve_source_identifier(
            document,
        )
        source_type = _resolve_source_type(
            document,
            source_identifier,
        )

        ingestion_pipeline = get_knowledge_ingestion_pipeline(
            source_type=source_type,
            request=request_context,
            session=session,
        )
        parsing_contract = getattr(
            ingestion_pipeline.parser,
            "parsing_contract",
            None,
        )
        logger.info(
            "Resolved ingestion parser: document_id=%s source_type=%s parser=%s provider=%s",
            document_id,
            source_type,
            type(ingestion_pipeline.parser).__name__,
            type(parsing_contract).__name__ if parsing_contract is not None else "none",
        )

        pipeline_request = _build_pipeline_request(
            document=document,
            source_path=source_identifier,
            source_type=source_type,
        )

        logger.info(
            "Starting background document ingestion",
            extra={
                "document_id": document_id,
                "source_type": source_type,
                "source_path": source_identifier,
            },
        )

        ingestion_pipeline.run(pipeline_request)

        document_service.mark_ready(
            MarkDocumentReadyCommand(
                document_id=document_id,
            )
        )
        session.commit()

        logger.info(
            "Background document ingestion completed",
            extra={
                "document_id": document_id,
                "source_type": source_type,
            },
        )

    except Exception as exc:
        logger.exception(
            "Background document ingestion failed",
            extra={
                "document_id": document_id,
            },
        )

        failure_session: Session | None = None
        try:
            if session is not None:
                _safe_rollback(session)
            if session_factory is None:
                session_factory = _get_app_session_factory(application)
            failure_session = session_factory()
            failed_document_service = get_document_application_service(
                request=request_context,
                session=failure_session,
            )
            failed_document_service.mark_failed(
                MarkDocumentFailedCommand(
                    document_id=document_id,
                    failure_reason=str(exc),
                )
            )
            failure_session.commit()
        except Exception:
            if failure_session is not None:
                _safe_rollback(failure_session)
            logger.exception(
                "Could not mark document as failed",
                extra={
                    "document_id": document_id,
                },
            )
        finally:
            if failure_session is not None:
                try:
                    failure_session.close()
                except Exception:
                    logger.exception(
                        "Could not close failure-status database session.",
                        extra={"document_id": document_id},
                    )

        return

    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                logger.exception(
                    "Could not close ingestion database session.",
                    extra={
                        "document_id": document_id,
                    },
                )


@router.post(
"/start",
response_model=IngestionResponse,
status_code=status.HTTP_202_ACCEPTED,
)
def start_ingestion(
    payload: StartIngestionRequest,
    request: Request,
) -> IngestionResponse:
    session_factory = _get_app_session_factory(request.app)
    session: Session = session_factory()

    try:
        document_service = get_document_application_service(
            request=request,
            session=session,
        )
        document = document_service.get_by_id(
            GetDocumentByIdQuery(
                document_id=payload.document_id,
            )
        )
        if document.status == "processing":
            last_updated = document.updated_at
            if last_updated.tzinfo is None:
                last_updated = last_updated.replace(tzinfo=timezone.utc)
            stale_after = request.app.state.settings.ingestion_stale_after_minutes
            if datetime.now(timezone.utc) - last_updated < timedelta(minutes=stale_after):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "document_ingestion_already_running",
                        "message": "This document is already processing. Retry after the configured stale-job timeout if it remains stuck.",
                    },
                )
        document_service.mark_pending(payload.document_id)
        session.commit()
    except HTTPException:
        _safe_rollback(session)
        raise
    except Exception as exc:
        logger.exception(
            "Manual document ingestion failed before background scheduling",
            extra={
                "document_id": payload.document_id,
            },
        )

        try:
            session.rollback()
        except Exception:
            logger.exception(
                "Manual ingestion rollback failed before background scheduling.",
                extra={
                    "document_id": payload.document_id,
                },
            )

        try:
            failed_document_service = get_document_application_service(
                request=request,
                session=session,
            )
            failed_document_service.mark_failed(
                MarkDocumentFailedCommand(
                    document_id=payload.document_id,
                    failure_reason=str(exc),
                )
            )
            session.commit()
        except Exception:
            logger.exception(
                "Could not mark document as failed before background scheduling",
                extra={
                    "document_id": payload.document_id,
                },
            )
            try:
                session.rollback()
            except Exception:
                logger.exception(
                    "Failed-session rollback also failed before background scheduling.",
                    extra={
                        "document_id": payload.document_id,
                    },
                )

        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "document_ingestion_failed",
                "message": "Document ingestion failed before scheduling.",
            },
        ) from exc
    finally:
        session.close()

    return IngestionResponse(
        document_id=str(payload.document_id),
        status="queued",
    )