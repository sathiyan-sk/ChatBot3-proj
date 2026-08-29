from __future__ import annotations

import logging
import time

from fastapi import Request
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse, Response

from app.config.settings import Settings

logger = logging.getLogger(__name__)

# Widget/client API paths get PER-APPLICATION CORS (resolved from the DB).
# All other routes (admin dashboard, docs, health, static widget assets)
# are handled by the global CORSMiddleware configured in main.py.
_WIDGET_API_PREFIXES = (
    "/api/client/widget",
    "/api/client/chat",
)

_LOCAL_ORIGIN_PREFIXES = (
    "http://localhost",
    "https://localhost",
    "http://127.0.0.1",
    "https://127.0.0.1",
)
_NULL_ORIGIN = "null"

_ALLOWED_METHODS = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
_ALLOWED_HEADERS = "Content-Type, Origin, X-Widget-Key, X-API-Key, Authorization"
_EXPOSED_HEADERS = "Content-Type, X-Widget-Key"
_MAX_AGE_SECONDS = "600"


def _normalize_origin(value: str) -> str:
    return value.strip().rstrip("/").lower()


class DynamicCorsMiddleware(BaseHTTPMiddleware):
    """Per-request CORS handling driven by application configuration.

    Production behaviour:
    - Widget/client API paths resolve the caller's application from the
      X-Widget-Key (widget public key) or X-API-Key (key prefix) header and
      validate the Origin header against that application's allowed_origins
      stored in the database (applications.allowed_origins).
    - First-party surfaces (admin dashboard, web chat) are handled by the
      global CORSMiddleware in main.py using the ALLOWED_ORIGINS env var.
    - Local development origins (localhost/127.0.0.1) and the file://
      "null" origin are optionally trusted (CORS_ALLOW_LOCAL_ORIGINS=true)
      so local widget testing keeps working without polluting production
      allow-lists. Set CORS_ALLOW_LOCAL_ORIGINS=false in production.
    """

    def __init__(
        self,
        app,
        *,
        settings: Settings,
        session_factory,
    ) -> None:
        super().__init__(app)
        self._settings = settings
        self._session_factory = session_factory
        # Short-lived cache: widget_key -> (frozenset[origins], expiry)
        self._cache: dict[str, tuple[frozenset[str], float]] = {}
        self._cache_ttl_seconds = 60.0

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin")
        path = request.url.path

        # Only widget/client API routes need per-application CORS.
        # First-party routes (admin, docs, health, static widget assets)
        # are handled by the global CORSMiddleware in main.py.
        if not origin or not self._is_widget_api_path(path):
            return await call_next(request)

        allowed = self._is_origin_allowed(request=request, origin=origin)

        if request.method == "OPTIONS":
            if not allowed:
                return PlainTextResponse(
                    "Origin not allowed for this widget.",
                    status_code=403,
                )
            preflight = PlainTextResponse("", status_code=200)
            preflight.headers["Access-Control-Allow-Origin"] = origin
            preflight.headers["Access-Control-Allow-Methods"] = _ALLOWED_METHODS
            preflight.headers["Access-Control-Allow-Headers"] = _ALLOWED_HEADERS
            preflight.headers["Access-Control-Max-Age"] = _MAX_AGE_SECONDS
            preflight.headers["Vary"] = "Origin"
            return preflight

        response = await call_next(request)

        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Expose-Headers"] = _EXPOSED_HEADERS

        return response

    def _is_origin_allowed(self, request: Request, origin: str) -> bool:
        normalized = _normalize_origin(origin)

        if self._settings.cors_allow_local_origins:
            if normalized == _NULL_ORIGIN:
                return True
            for prefix in _LOCAL_ORIGIN_PREFIXES:
                if normalized.startswith(prefix):
                    return True

        widget_key = (
            request.headers.get("X-Widget-Key")
            or request.headers.get("X-API-Key")
            or ""
        ).strip()

        if not widget_key:
            return False

        return normalized in self._allowed_origins_for_key(
            widget_key=widget_key,
        )

    def _allowed_origins_for_key(self, widget_key: str) -> frozenset[str]:
        now = time.monotonic()

        cached = self._cache.get(widget_key)
        if cached is not None and now < cached[1]:
            return cached[0]

        # Flush expired entries to bound memory.
        expired = [
            key
            for key, (_, expiry) in self._cache.items()
            if expiry <= now
        ]
        for key in expired:
            self._cache.pop(key, None)

        session = self._session_factory()
        try:
            rows = session.execute(
                text(
                    """
                    select a.allowed_origins
                    from applications a
                    where a.is_active = true
                      and (
                        exists (
                            select 1 from widgets w
                            where w.application_id = a.id
                              and w.public_key = :widget_key
                              and w.is_enabled = true
                        )
                        or exists (
                            select 1 from api_keys ak
                            where ak.application_id = a.id
                              and ak.is_active = true
                              and :widget_key like (ak.key_prefix || '%')
                        )
                      )
                    """
                ),
                {"widget_key": widget_key},
            ).scalars().all()

            origins: set[str] = set()
            for raw in rows:
                # allowed_origins is a Postgres text[] -> list of strings.
                if raw is None:
                    continue
                items = raw if isinstance(raw, (list, tuple)) else [raw]
                for item in items:
                    if item and str(item).strip():
                        origins.add(_normalize_origin(str(item)))

            result = frozenset(origins)
            self._cache[widget_key] = (
                result,
                now + self._cache_ttl_seconds,
            )
            return result
        except Exception:
            # Fail closed: if the DB is unreachable, do not open CORS.
            logger.exception("Dynamic CORS origin lookup failed")
            return frozenset()
        finally:
            session.close()

    @staticmethod
    def _is_widget_api_path(path: str) -> bool:
        return any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in _WIDGET_API_PREFIXES
        )


def register_dynamic_cors_middleware(
    app,
    *,
    settings: Settings,
    session_factory,
) -> None:
    """Attach the per-application CORS middleware.

    Must be added BEFORE (i.e. outermost relative to) the global
    CORSMiddleware so widget routes short-circuit with DB-driven origins.
    """
    app.add_middleware(
        DynamicCorsMiddleware,
        settings=settings,
        session_factory=session_factory,
    )
