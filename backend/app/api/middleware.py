from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config.security import SecuritySettings
from app.core.constants import REQUEST_START_TIME_KEY
from app.core.ids import generate_uuid
from app.infrastructure.observability.logging import (
    reset_request_id,
    set_request_id,
)
from app.infrastructure.observability.metrics import InMemoryMetricsRegistry

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: FastAPI,
        *,
        request_id_header_name: str,
        metrics_registry: InMemoryMetricsRegistry,
    ) -> None:
        super().__init__(app)
        self._request_id_header_name = request_id_header_name
        self._metrics_registry = metrics_registry

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get(self._request_id_header_name, generate_uuid())
        request_id_token = set_request_id(request_id)
        request.state.request_id = request_id
        request.state.__dict__[REQUEST_START_TIME_KEY] = time.perf_counter()

        self._metrics_registry.increment("http_requests_total")

        try:
            try:
                response = await call_next(request)
            except Exception:
                self._metrics_registry.increment("http_requests_failed_total")
                raise

            duration_ms = (
                time.perf_counter()
                - request.state.__dict__[REQUEST_START_TIME_KEY]
            ) * 1000
            response.headers[self._request_id_header_name] = request_id
            response.headers["X-Process-Time-Ms"] = f"{duration_ms:.2f}"

            logger.info(
                "HTTP request completed | request_id=%s method=%s path=%s status=%s duration_ms=%.2f",
                request_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            reset_request_id(request_id_token)


def register_middlewares(
    app: FastAPI,
    *,
    security_settings: SecuritySettings,
    metrics_registry: InMemoryMetricsRegistry,
) -> None:
    app.add_middleware(
        RequestContextMiddleware,
        request_id_header_name=security_settings.request_id_header_name,
        metrics_registry=metrics_registry,
    )