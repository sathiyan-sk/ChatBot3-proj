from __future__ import annotations

import logging
import time
from urllib.parse import urlsplit

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
        # Origin allow-lists are mutable through the admin UI and should not be
        # cached across requests: a stale cached allow-list can continue denying
        # a valid production origin even after the application config was updated.
        self._cache: dict[str, tuple[frozenset[str], float]] = {}
        self._cache_ttl_seconds = 0.0

    def clear_cache(self, widget_key: str | None = None) -> None:
        """Clear cache for a specific widget key or all cache if widget_key is None."""
        if widget_key:
            self._cache.pop(widget_key, None)
            logger.debug(f"Cleared CORS cache for widget_key: {widget_key}")
        else:
            self._cache.clear()
            logger.debug("Cleared all CORS cache")

    async def dispatch(self, request: Request, call_next) -> Response:
        origin = request.headers.get("origin")
        path = request.url.path

        # Only widget/client API routes need per-application CORS.
        # First-party routes (admin, docs, health, static widget assets)
        # are handled by the global CORSMiddleware in main.py.
        if not self._is_widget_api_path(path):
            return await call_next(request)

        # Handle OPTIONS preflight requests even without Origin header
        if request.method == "OPTIONS" and not origin:
            logger.debug(f"OPTIONS preflight without origin for {path}")
            preflight = PlainTextResponse("", status_code=200)
            preflight.headers["Access-Control-Allow-Methods"] = _ALLOWED_METHODS
            preflight.headers["Access-Control-Allow-Headers"] = _ALLOWED_HEADERS
            preflight.headers["Access-Control-Max-Age"] = _MAX_AGE_SECONDS
            return preflight

        if not origin:
            return await call_next(request)

        try:
            allowed = self._is_origin_allowed(request=request, origin=origin)
            logger.debug(f"Origin {origin} allowed={allowed} for {path}")
        except Exception:
            logger.exception(f"Error checking origin {origin} for {path}")
            if request.method == "OPTIONS":
                return PlainTextResponse("CORS check failed", status_code=400)
            return await call_next(request)

        if request.method == "OPTIONS":
            if not allowed:
                logger.info(f"Rejecting origin {origin} for {path}")
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
            logger.debug(f"Allowing origin {origin} for {path}")
            return preflight

        response = await call_next(request)

        if allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Expose-Headers"] = _EXPOSED_HEADERS

        return response

    @staticmethod
    def _is_local_origin(origin: str) -> bool:
        normalized = _normalize_origin(origin)
        if normalized == _NULL_ORIGIN:
            return True
        try:
            parsed = urlsplit(normalized)
            port = parsed.port
        except ValueError:
            return False
        return (
            parsed.scheme in {"http", "https"}
            and parsed.hostname in {"localhost", "127.0.0.1"}
            and parsed.username is None
            and parsed.password is None
            and parsed.path in {"", "/"}
            and not parsed.query
            and not parsed.fragment
            and (port is None or 0 < port <= 65535)
        )

    def _is_origin_allowed(self, request: Request, origin: str) -> bool:
        normalized = _normalize_origin(origin)
        logger.debug(f"Checking origin: {origin} -> normalized: {normalized}")

        if self._settings.cors_allow_local_origins and self._is_local_origin(normalized):
            logger.debug(f"Origin matches local prefix/dev origin: {origin}")
            return True

        widget_key = (
            request.headers.get("X-Widget-Key")
            or request.headers.get("X-API-Key")
            or ""
        ).strip()

        if not widget_key:
            logger.debug(f"No widget key in headers for origin {origin}")
            if request.method == "OPTIONS":
                requested_headers = {
                    header.strip().lower()
                    for header in (
                        request.headers.get("access-control-request-headers") or ""
                    ).split(",")
                }
                path = request.url.path
                widget_key_preflight = (
                    "x-widget-key" in requested_headers
                    and (
                        path.startswith("/api/client/widget/")
                        or path == "/api/client/chat/widget/messages"
                    )
                )
                api_key_preflight = (
                    "x-api-key" in requested_headers
                    and path == "/api/client/chat/messages"
                )
                if widget_key_preflight or api_key_preflight:
                    logger.debug("Preflight includes the expected key header for the client route")
                    return True
            return False

        trusted_frontend_origins = {
            _normalize_origin(configured_origin)
            for configured_origin in getattr(
                self._settings,
                "cors_allowed_origins",
                (),
            )
        }
        if (
            request.url.path == "/api/client/chat/messages"
            and normalized in trusted_frontend_origins
        ):
            return True

        allowed_origins = self._allowed_origins_for_key(widget_key=widget_key)

        # A failed database lookup is different from an intentionally empty
        # allow-list. Fail closed when the configured policy cannot be read.
        if allowed_origins is None:
            return False
        
        # If allowed_origins is empty, allow all origins (permissive mode)
        if not allowed_origins:
            logger.debug(f"Widget key {widget_key} has no allowed origins configured - allowing all origins")
            return True
        
        is_allowed = normalized in allowed_origins
        logger.debug(f"Widget key {widget_key}: allowed_origins={allowed_origins}, is_allowed={is_allowed}")
        return is_allowed

    def _allowed_origins_for_key(self, widget_key: str) -> frozenset[str] | None:
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

        session = None
        try:
            session = self._session_factory()
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
            logger.debug(f"Cached origins for {widget_key}: {result}")
            return result
        except Exception:
            # Fail closed: if the DB is unreachable, do not open CORS.
            logger.exception(f"Dynamic CORS origin lookup failed for widget_key={widget_key}")
            return None
        finally:
            if session is not None:
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
) -> DynamicCorsMiddleware:
    """Attach the per-application CORS middleware.

    Must be added BEFORE (i.e. outermost relative to) the global
    CORSMiddleware so widget routes short-circuit with DB-driven origins.
    
    Returns the middleware instance so it can be stored for cache clearing.
    """
    middleware = DynamicCorsMiddleware(
        app,
        settings=settings,
        session_factory=session_factory,
    )
    app.add_middleware(
        DynamicCorsMiddleware,
        settings=settings,
        session_factory=session_factory,
    )
    
    # Store reference for cache clearing
    app.state.dynamic_cors_middleware = middleware
    
    return middleware
