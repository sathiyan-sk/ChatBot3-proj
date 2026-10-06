from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.ingestion import run_document_ingestion_worker
from app.api.dependencies import get_knowledge_ingestion_pipeline
from app.api.dynamic_cors import register_dynamic_cors_middleware
from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.composition import build_application_container
from app.config.settings import get_settings
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
)

logger = logging.getLogger(__name__)


def _cleanup_expired_conversations(session_factory, default_retention_days: int) -> int:
    session = session_factory()
    try:
        deleted_count = SqlAlchemyConversationRepository(
            session
        ).delete_expired_conversations(
            default_retention_days=default_retention_days,
        )
        session.commit()
        return deleted_count
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _run_retention_cleanup(session_factory, default_retention_days: int) -> None:
    while True:
        await asyncio.sleep(60 * 60)
        try:
            deleted_count = await asyncio.to_thread(
                _cleanup_expired_conversations,
                session_factory,
                default_retention_days,
            )
            if deleted_count:
                logger.info("Removed %s expired conversations", deleted_count)
        except Exception:
            logger.exception("Scheduled conversation-retention cleanup failed")


def create_lifespan(settings, session_factory):
    """Factory for lifespan context manager with dependency injection."""
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.session_factory = session_factory

        # Ensure vector store schema exists before serving requests
        session = session_factory()
        try:
            vector_provider = PgVectorProvider(settings=settings, session=session)
            vector_provider.ensure_schema()
        finally:
            session.close()

        app.state.container = build_application_container(
            settings=settings,
            session_factory=session_factory,
        )
        app.state.knowledge_ingestion_pipeline_factory = (
            get_knowledge_ingestion_pipeline
        )

        ingestion_workers = [
            asyncio.create_task(
                run_document_ingestion_worker(
                    session_factory,
                    application=app,
                    worker_id=worker_id,
                    stale_after_minutes=settings.ingestion_stale_after_minutes,
                )
            )
            for worker_id in range(1, settings.document_ingestion_concurrency + 1)
        ]
        logger.info(
            "Started %s document ingestion worker(s)",
            len(ingestion_workers),
        )

        try:
            deleted_count = await asyncio.to_thread(
                _cleanup_expired_conversations,
                session_factory,
                settings.chat_history_retention_days,
            )
            if deleted_count:
                logger.info("Removed %s expired conversations at startup", deleted_count)
        except Exception:
            logger.exception("Startup conversation-retention cleanup failed")

        retention_task = asyncio.create_task(
            _run_retention_cleanup(
                session_factory,
                settings.chat_history_retention_days,
            )
        )

        try:
            yield
        finally:
            retention_task.cancel()
            try:
                await retention_task
            except asyncio.CancelledError:
                pass
            for worker in ingestion_workers:
                worker.cancel()
            await asyncio.gather(*ingestion_workers, return_exceptions=True)
    
    return lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    session_factory = create_session_factory(settings.database.url)

    app = FastAPI(
        title="AI Knowledge Platform Backend",
        version="1.0.0",
        lifespan=create_lifespan(settings, session_factory),
    )

    # Global CORS is added first so Starlette executes it before the
    # per-application widget middleware. The widget middleware must still be
    # the last custom handler in the stack so it can short-circuit the DB-driven
    # origin checks for /api/client/* requests.
    cors_origins = list(settings.cors_allowed_origins) if settings.cors_allowed_origins else []
    if settings.cors_allow_local_origins and "http://localhost:3000" not in cors_origins:
        cors_origins.extend([
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:5173",
        ])

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if settings.cors_allow_local_origins else None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Origin", "X-Widget-Key", "X-API-Key", "Authorization", "Access-Control-Request-Headers", "Access-Control-Request-Method"],
        expose_headers=["Content-Type", "X-Widget-Key"],
    )

    register_dynamic_cors_middleware(
        app,
        settings=settings,
        session_factory=session_factory,
    )

    register_exception_handlers(app)
    app.include_router(api_router)

    @app.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "OK"}

    return app


app = create_app()