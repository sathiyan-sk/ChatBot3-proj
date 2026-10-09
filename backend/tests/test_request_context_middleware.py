from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.middleware import register_middlewares
from app.config.security import SecuritySettings
from app.infrastructure.observability.metrics import InMemoryMetricsRegistry


def _test_app():
    app = FastAPI()
    register_middlewares(
        app,
        security_settings=SecuritySettings(
            admin_username="admin",
            admin_password="password",
            api_key_header_name="X-API-Key",
            request_id_header_name="X-Request-ID",
        ),
        metrics_registry=InMemoryMetricsRegistry(),
    )

    @app.get("/request-id")
    def get_request_id(request: Request):
        return {"request_id": request.state.request_id}

    return app


def test_request_context_middleware_preserves_supplied_request_id():
    with TestClient(_test_app()) as client:
        response = client.get(
            "/request-id",
            headers={"X-Request-ID": "chat-request-123"},
        )

    assert response.status_code == 200
    assert response.json() == {"request_id": "chat-request-123"}
    assert response.headers["X-Request-ID"] == "chat-request-123"


def test_request_context_middleware_generates_missing_request_id():
    with TestClient(_test_app()) as client:
        supplied_response = client.get(
            "/request-id",
            headers={"X-Request-ID": "first-request"},
        )
        response = client.get("/request-id")

    assert response.status_code == 200
    assert response.json()["request_id"]
    assert response.json()["request_id"] != "first-request"
    assert response.headers["X-Request-ID"] == response.json()["request_id"]
    assert supplied_response.headers["X-Request-ID"] == "first-request"