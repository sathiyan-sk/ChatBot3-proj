from __future__ import annotations

import asyncio
import logging
import multiprocessing
import os
import queue as queue_module
import random
import socket
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    status,
)
from sqlalchemy import and_, or_, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.dependencies import (
    build_document_application_service,
    build_knowledge_ingestion_pipeline,
    get_document_application_service,
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
)
from app.modules.documents.application.queries import (
    GetDocumentByIdQuery,
)
from app.config.settings import Settings
from app.core.exceptions import ApplicationError

logger = logging.getLogger(__name__)

class IngestionApplication(Protocol):
    @property
    def state(self) -> Any: ...


class IngestionResultQueue(Protocol):
    def put(self, item: tuple[str, str | None]) -> None: ...

    def get(self, timeout: float) -> tuple[str, str | None]: ...


@dataclass(slots=True)
class _IngestionAppState:
    settings: Settings
    session_factory: Callable[[], Session]


@dataclass(slots=True)
class _IngestionApplication:
    state: _IngestionAppState


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
    ingestion_version: int,
) -> KnowledgeIngestionPipelineRequest:
    return KnowledgeIngestionPipelineRequest(
        document_id=str(getattr(document, "id", "")),
        knowledge_base_id=str(getattr(document, "knowledge_base_id", "")),
        source_type=source_type,
        source_path=source_path,
        source_identifier=source_path,
        ingestion_version=ingestion_version,
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


def _get_app_session_factory(
    app: IngestionApplication,
) -> Callable[[], Session]:
    session_factory = getattr(app.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError(
            "Application database session factory is not initialized.",
        )
    return session_factory


def claim_next_pending_document(
    session_factory,
    stale_after_minutes: int = 120,
    *,
    worker_id: int | None = None,
    lease_seconds: int = 120,
    max_attempts: int = 3,
) -> tuple[str, int] | None:
    session: Session = session_factory()
    try:
        now = datetime.now(timezone.utc)
        stale_before = now - timedelta(minutes=stale_after_minutes)
        document = session.execute(
            select(DocumentModel)
            .where(
                or_(
                    and_(
                        DocumentModel.status == "pending",
                        or_(
                            DocumentModel.ingestion_next_attempt_at.is_(None),
                            DocumentModel.ingestion_next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        DocumentModel.status == "processing",
                        or_(
                            DocumentModel.ingestion_lease_expires_at <= now,
                            and_(
                                DocumentModel.ingestion_lease_expires_at.is_(None),
                                DocumentModel.updated_at < stale_before,
                            ),
                        ),
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
        queued_at = document.updated_at
        attempt_count = getattr(document, "ingestion_attempt_count", 0)
        if attempt_count >= max_attempts:
            document.status = "failed"
            document.failure_code = "ingestion_retry_exhausted"
            document.failure_reason = (
                f"Document ingestion reached the maximum of {max_attempts} attempts."
            )
            document.ingestion_lease_expires_at = None
            document.ingestion_next_attempt_at = None
            document.updated_at = now
            session.commit()
            logger.error(
                "Document ingestion moved to terminal failure after retry limit",
                extra={
                    "document_id": str(document.id),
                    "attempt_count": attempt_count,
                },
            )
            return None

        document.ingestion_version += 1
        document.ingestion_attempt_count = attempt_count + 1
        document.status = "processing"
        document.failure_code = None
        document.failure_reason = None
        claimed_at = datetime.now(timezone.utc)
        document.updated_at = claimed_at
        document.ingestion_next_attempt_at = None
        document.ingestion_lease_expires_at = claimed_at + timedelta(
            seconds=max(60, lease_seconds)
        )
        document_id = str(document.id)
        ingestion_version = document.ingestion_version
        session.commit()
        if queued_at.tzinfo is None:
            queued_at = queued_at.replace(tzinfo=timezone.utc)
        logger.info(
            "Claimed document ingestion job",
            extra={
                "document_id": document_id,
                "ingestion_version": ingestion_version,
                "attempt_count": document.ingestion_attempt_count,
                "reclaimed_stale_job": was_stale,
                "queue_wait_seconds": max(
                    0,
                    int((claimed_at - queued_at).total_seconds()),
                ),
                "worker_id": worker_id,
                "worker_host": socket.gethostname(),
                "worker_process_id": os.getpid(),
            },
        )
        return document_id, ingestion_version
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def run_document_ingestion_worker(
    session_factory,
    *,
    application: IngestionApplication,
    worker_id: int,
    stale_after_minutes: int = 120,
    poll_interval_seconds: float = 2.0,
    ingestion_timeout_seconds: int | None = None,
    lease_seconds: int = 120,
) -> None:
    logger.info("Document ingestion worker started", extra={"worker_id": worker_id})
    while True:
        try:
            claimed_job = await asyncio.to_thread(
                claim_next_pending_document,
                session_factory,
                stale_after_minutes,
                worker_id=worker_id,
                lease_seconds=lease_seconds,
                max_attempts=getattr(
                    application.state.settings,
                    "ingestion_max_attempts",
                    3,
                ),
            )
            if claimed_job is None:
                await asyncio.sleep(poll_interval_seconds)
                continue
            document_id, ingestion_version = claimed_job

            timeout_value = (
                ingestion_timeout_seconds
                if ingestion_timeout_seconds is not None
                else getattr(application.state.settings, "ingestion_timeout_seconds", 300)
            )

            await asyncio.to_thread(
                _execute_document_ingestion_with_timeout,
                document_id,
                application,
                timeout_seconds=timeout_value,
                ingestion_version=ingestion_version,
                lease_seconds=lease_seconds,
            )
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
    ingestion_version: int,
    *,
    lease_seconds: int = 120,
) -> bool:
    session: Session = session_factory()
    try:
        now = datetime.now(timezone.utc)
        result = session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.status == "processing",
                DocumentModel.ingestion_version == ingestion_version,
                DocumentModel.ingestion_lease_expires_at > now,
            )
            .values(
                updated_at=now,
                ingestion_lease_expires_at=now
                + timedelta(seconds=max(60, lease_seconds)),
            )
        )
        session.commit()
        return result.rowcount == 1
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _mark_document_failed_and_log(
    session_factory: Callable[[], Session],
    document_id: str,
    reason: str,
    ingestion_version: int,
    *,
    failure_code: str = "ingestion_failed",
) -> None:
    session: Session | None = None
    try:
        active_session = session_factory()
        session = active_session
        result = active_session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.ingestion_version == ingestion_version,
                DocumentModel.status == "processing",
                DocumentModel.ingestion_lease_expires_at
                > datetime.now(timezone.utc),
            )
            .values(
                status="failed",
                failure_code=failure_code,
                failure_reason=reason,
                ingestion_lease_expires_at=None,
                ingestion_next_attempt_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount != 1:
            active_session.rollback()
            logger.warning(
                "Skipped failure update because this attempt is no longer processing",
                extra={
                    "document_id": document_id,
                    "ingestion_version": ingestion_version,
                },
            )
            return
        active_session.commit()
        logger.error(
            "Document ingestion failed and was marked failed",
            extra={
                "document_id": document_id,
                "ingestion_version": ingestion_version,
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
    queue: IngestionResultQueue | None = None,
    ingestion_version: int | None = None,
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
        application = _IngestionApplication(
            state=_IngestionAppState(
                settings=settings,
                session_factory=session_factory,
            )
        )
        run_document_ingestion_task(
            document_id,
            application,
            ingestion_version=ingestion_version,
        )
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


def _retry_delay_seconds(attempt_count: int, settings: Settings) -> float:
    ceiling = max(1.0, settings.ingestion_retry_max_seconds)
    base = max(1.0, settings.ingestion_retry_base_seconds)
    exponential_delay = min(ceiling, base * (2 ** max(0, attempt_count - 1)))
    return random.uniform(exponential_delay * 0.75, exponential_delay)


def _is_retryable_ingestion_error(error: Exception) -> bool:
    if not isinstance(error, ApplicationError) or not error.details:
        return False
    return error.details.get("retryable") is True


def _terminate_ingestion_process(process) -> None:
    if not process.is_alive():
        return
    process.terminate()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join(5)


def _record_ingestion_failure(
    session_factory: Callable[[], Session],
    document_id: str,
    error: Exception,
    ingestion_version: int,
    settings: Settings,
) -> None:
    session = session_factory()
    try:
        now = datetime.now(timezone.utc)
        document = session.execute(
            select(DocumentModel).where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.ingestion_version == ingestion_version,
                DocumentModel.status == "processing",
                DocumentModel.ingestion_lease_expires_at > now,
            )
        ).scalar_one_or_none()
        if document is None:
            session.rollback()
            logger.warning(
                "Failure update skipped because ingestion lease was lost",
                extra={
                    "document_id": document_id,
                    "ingestion_version": ingestion_version,
                },
            )
            return

        max_attempts = max(1, settings.ingestion_max_attempts)
        retry = (
            _is_retryable_ingestion_error(error)
            and document.ingestion_attempt_count < max_attempts
        )
        failure_code = getattr(error, "code", "ingestion_failed")
        values: dict[str, object] = {
            "status": "pending" if retry else "failed",
            "failure_code": failure_code,
            "failure_reason": str(error),
            "ingestion_lease_expires_at": None,
            "updated_at": now,
            "ingestion_next_attempt_at": (
                now
                + timedelta(
                    seconds=_retry_delay_seconds(
                        document.ingestion_attempt_count,
                        settings,
                    )
                )
                if retry
                else None
            ),
        }
        result = session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.ingestion_version == ingestion_version,
                DocumentModel.status == "processing",
                DocumentModel.ingestion_lease_expires_at > now,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            session.rollback()
            logger.warning(
                "Failure update skipped because ingestion lease was lost",
                extra={
                    "document_id": document_id,
                    "ingestion_version": ingestion_version,
                },
            )
            return
        session.commit()
        logger.log(
            logging.WARNING if retry else logging.ERROR,
            "Document ingestion attempt %s",
            "scheduled for retry" if retry else "failed permanently",
            extra={
                "document_id": document_id,
                "ingestion_version": ingestion_version,
                "failure_code": failure_code,
                "attempt_count": document.ingestion_attempt_count,
                "next_attempt_at": values["ingestion_next_attempt_at"],
            },
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _execute_document_ingestion_with_timeout(
    document_id: str,
    application: IngestionApplication,
    *,
    timeout_seconds: int,
    ingestion_version: int,
    lease_seconds: int = 120,
    heartbeat_interval_seconds: int = 30,
) -> None:
    if timeout_seconds <= 0:
        timeout_seconds = 300

    session_factory = getattr(application.state, "session_factory", None)
    if session_factory is None:
        raise RuntimeError(
            "Application database session factory is not initialized."
        )

    lock_session: Session = session_factory()
    try:
        lock_acquired = lock_session.execute(
            text(
                "SELECT pg_try_advisory_xact_lock("
                "hashtextextended(:document_id, 0))"
            ),
            {"document_id": document_id},
        ).scalar_one()
    except Exception:
        lock_session.close()
        raise

    if not lock_acquired:
        lock_session.close()
        logger.warning(
            "Skipping duplicate document ingestion execution; another worker owns the lock",
            extra={"document_id": document_id},
        )
        return

    try:
        context = multiprocessing.get_context("spawn")
        queue_factory = getattr(context, "Queue", None) or multiprocessing.Queue
        queue = queue_factory()
        process = context.Process(
            target=_run_document_ingestion_task_in_subprocess,
            args=(document_id, queue, ingestion_version),
        )
        process.start()
        deadline = time.monotonic() + timeout_seconds
        while process.is_alive():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            process.join(timeout=min(heartbeat_interval_seconds, remaining))
            if not process.is_alive():
                break
            try:
                renewed = touch_document_ingestion_heartbeat(
                    session_factory,
                    document_id,
                    ingestion_version,
                    lease_seconds=lease_seconds,
                )
            except Exception as exc:
                logger.exception(
                    "Could not renew document ingestion lease; terminating worker process",
                    extra={
                        "document_id": document_id,
                        "ingestion_version": ingestion_version,
                    },
                )
                _terminate_ingestion_process(process)
                raise RuntimeError(
                    "Document ingestion lease could not be renewed; "
                    "the attempt will be recovered after lease expiry."
                ) from exc
            if not renewed:
                logger.warning(
                    "Terminating document ingestion after lease ownership was lost",
                    extra={
                        "document_id": document_id,
                        "ingestion_version": ingestion_version,
                    },
                )
                _terminate_ingestion_process(process)
                raise RuntimeError(
                    "Document ingestion lease expired or was superseded."
                )

        if process.is_alive():
            logger.warning(
                "Document ingestion exceeded timeout; terminating worker process",
                extra={
                    "document_id": document_id,
                    "timeout_seconds": timeout_seconds,
                },
            )
            _terminate_ingestion_process(process)
            _mark_document_failed_and_log(
                session_factory,
                document_id,
                f"Document ingestion timed out after {timeout_seconds} seconds.",
                ingestion_version,
                failure_code="ingestion_timeout",
            )
            raise TimeoutError(
                f"Document ingestion timed out after {timeout_seconds} seconds."
            )

        try:
            result_status, payload = queue.get(timeout=5)
        except queue_module.Empty as exc:
            if process.exitcode not in (0, None):
                reason = (
                    "Document ingestion process exited unexpectedly with code "
                    f"{process.exitcode}."
                )
                raise RuntimeError(reason) from exc
            logger.exception(
                "Document ingestion subprocess exited without reporting a result",
                extra={"document_id": document_id},
            )
            raise RuntimeError(
                "Document ingestion subprocess exited without reporting a result."
            ) from exc
        if result_status == "error":
            reason = payload or "document ingestion failed"
            raise RuntimeError(reason)
        if process.exitcode not in (0, None):
            reason = (
                "Document ingestion process exited unexpectedly with code "
                f"{process.exitcode}."
            )
            raise RuntimeError(reason)
        if result_status != "success":
            raise RuntimeError(
                f"Document ingestion subprocess returned unknown status: {result_status}."
            )
    finally:
        lock_session.close()


def run_document_ingestion_task(
    document_id: str,
    application: IngestionApplication | None = None,
    *,
    ingestion_version: int | None = None,
) -> None:
    if application is None:
        from app.main import app

        application = app

    session_factory = None
    session: Session | None = None

    try:
        session_factory = _get_app_session_factory(application)
        active_session = session_factory()
        session = active_session
        logger.info(
            "Document ingestion task started",
            extra={"document_id": document_id},
        )
        document_service = build_document_application_service(
            settings=application.state.settings,
            session=active_session,
        )

        document = document_service.get_by_id(
            GetDocumentByIdQuery(
                document_id=document_id,
            )
        )
        if (
            ingestion_version is not None
            and document.ingestion_version != ingestion_version
        ):
            raise RuntimeError(
                "Document ingestion attempt was superseded before processing."
            )
        if ingestion_version is None:
            raise RuntimeError(
                "Document ingestion version is required to process this attempt."
            )

        document_service.mark_processing(
            MarkDocumentProcessingCommand(
                document_id=document_id,
            )
        )
        active_session.commit()

        source_identifier = _resolve_source_identifier(
            document,
        )
        source_type = _resolve_source_type(
            document,
            source_identifier,
        )

        ingestion_pipeline = build_knowledge_ingestion_pipeline(
            source_type=source_type,
            settings=application.state.settings,
            session=active_session,
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
            ingestion_version=ingestion_version,
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

        published = active_session.execute(
            update(DocumentModel)
            .where(
                DocumentModel.id == UUID(document_id),
                DocumentModel.status == "processing",
                DocumentModel.ingestion_version == ingestion_version,
                DocumentModel.ingestion_lease_expires_at
                > datetime.now(timezone.utc),
            )
            .values(
                status="ready",
                ready_version=ingestion_version,
                failure_code=None,
                failure_reason=None,
                ingestion_lease_expires_at=None,
                ingestion_next_attempt_at=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if published.rowcount != 1:
            raise RuntimeError(
                "Document ingestion attempt was superseded before publication."
            )
        delete_obsolete_versions = getattr(
            ingestion_pipeline.vector_indexer.vector_store_contract,
            "delete_obsolete_document_versions",
            None,
        )
        if not callable(delete_obsolete_versions):
            raise RuntimeError(
                "Vector store cannot safely retire obsolete document versions."
            )
        delete_obsolete_versions(
            document_id=document_id,
            keep_version=ingestion_version,
        )
        active_session.commit()

        logger.info(
            "Background document ingestion completed",
            extra={
                "document_id": document_id,
                "ingestion_version": ingestion_version,
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
            active_failure_session = session_factory()
            failure_session = active_failure_session
            if ingestion_version is not None:
                _safe_rollback(active_failure_session)
                active_failure_session.close()
                failure_session = None
                _record_ingestion_failure(
                    session_factory,
                    document_id,
                    exc,
                    ingestion_version,
                    application.state.settings,
                )
            else:
                failed_document_service = build_document_application_service(
                    settings=application.state.settings,
                    session=active_failure_session,
                )
                failed_document_service.mark_failed(
                    MarkDocumentFailedCommand(
                        document_id=document_id,
                        failure_reason=str(exc),
                    )
                )
                active_failure_session.commit()
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

        raise

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
    try:
        document_uuid = UUID(payload.document_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "document_id_invalid",
                "message": "Document ID must be a valid UUID.",
            },
        ) from exc

    session_factory = _get_app_session_factory(request.app)
    session: Session = session_factory()

    try:
        document_row = session.execute(
            select(DocumentModel)
            .where(DocumentModel.id == document_uuid)
            .with_for_update()
        ).scalar_one_or_none()
        if document_row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "document_not_found",
                    "message": "Document not found.",
                },
            )

        document_service = get_document_application_service(
            request=request,
            session=session,
        )
        document = document_service.get_by_id(
            GetDocumentByIdQuery(
                document_id=payload.document_id,
            )
        )
        if document_row.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "document_ingestion_already_queued",
                    "message": "This document is already queued for ingestion.",
                },
            )
        if document_row.status == "processing":
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
        document_row.ingestion_attempt_count = 0
        document_row.ingestion_next_attempt_at = None
        document_row.ingestion_lease_expires_at = None
        document_row.failure_code = None
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