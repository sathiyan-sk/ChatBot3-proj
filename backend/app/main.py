from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.dependencies import get_knowledge_ingestion_pipeline
from app.api.dynamic_cors import register_dynamic_cors_middleware
from app.api.error_handlers import register_exception_handlers
from app.api.router import api_router
from app.composition import build_application_container
from app.config.settings import get_settings
from app.infrastructure.db.session import create_session_factory
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider


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

        yield
    
    return lifespan


def create_app() -> FastAPI:
    settings = get_settings()
    session_factory = create_session_factory(settings.database.url)

    app = FastAPI(
        title="AI Knowledge Platform Backend",
        version="1.0.0",
        lifespan=create_lifespan(settings, session_factory),
    )

    # Register per-application dynamic CORS BEFORE global CORS.
    # Widget/client routes will use DB-driven origins; others fall through to global CORS.
    register_dynamic_cors_middleware(
        app,
        settings=settings,
        session_factory=session_factory,
    )

    # Global CORS for first-party surfaces (admin dashboard, web chat).
    # Widget/client API origins are resolved per-application from the database.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins) if settings.cors_allowed_origins else [],
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?" if settings.cors_allow_local_origins else None,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Origin", "X-Widget-Key", "X-API-Key", "Authorization"],
        expose_headers=["Content-Type", "X-Widget-Key"],
    )

    register_exception_handlers(app)
    app.include_router(api_router)
    # Serve the embeddable widget static assets (widget.js, widget.css) so that
    # client websites can load the widget from the backend origin - the same
    # origin they already use for API calls.
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/widget", StaticFiles(directory=static_dir / "widget"), name="widget")

    @app.get("/health", tags=["Health"])
    def health_check() -> dict[str, str]:
        return {"status": "OK"}

    return app


app = create_app()