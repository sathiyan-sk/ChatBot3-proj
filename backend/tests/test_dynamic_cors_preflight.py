from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dynamic_cors import DynamicCorsMiddleware
from app.infrastructure.security.origin_validator import OriginValidator
from app.main import app


def test_widget_preflight_from_localhost_is_allowed():
    client = TestClient(app)

    response = client.options(
        "/api/client/widget/configuration",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Widget-Key, Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_local_origin_matching_rejects_lookalike_hosts():
    validator = OriginValidator()

    allowed_origins = ["https://client.example"]

    assert validator.is_allowed("http://localhost:5173", allowed_origins)
    assert not validator.is_allowed("http://localhost.attacker.example", allowed_origins)
    assert not validator.is_allowed("https://127.0.0.1.attacker.example", allowed_origins)


def test_dynamic_cors_fails_closed_when_origin_lookup_fails():
    class FailedSession:
        def execute(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

        def close(self):
            pass

    middleware = DynamicCorsMiddleware(
        lambda scope, receive, send: None,
        settings=SimpleNamespace(cors_allow_local_origins=False),
        session_factory=FailedSession,
    )
    request = SimpleNamespace(
        headers={"X-Widget-Key": "public-key"},
        method="GET",
    )

    assert not middleware._is_origin_allowed(request, "https://client.example")


def test_dynamic_cors_keeps_empty_allow_list_permissive():
    class EmptySession:
        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [])
            )

        def close(self):
            pass

    middleware = DynamicCorsMiddleware(
        lambda scope, receive, send: None,
        settings=SimpleNamespace(cors_allow_local_origins=False),
        session_factory=EmptySession,
    )
    request = SimpleNamespace(
        headers={"X-Widget-Key": "public-key"},
        method="GET",
    )

    assert middleware._is_origin_allowed(request, "https://client.example")


def test_api_key_preflight_is_accepted_for_client_chat():
    middleware = DynamicCorsMiddleware(
        lambda scope, receive, send: None,
        settings=SimpleNamespace(
            cors_allow_local_origins=False,
            cors_allowed_origins=(),
        ),
        session_factory=lambda: None,
    )
    request = SimpleNamespace(
        headers={
            "access-control-request-headers": "content-type, x-api-key",
        },
        method="OPTIONS",
        url=SimpleNamespace(path="/api/client/chat/messages"),
    )

    assert middleware._is_origin_allowed(request, "https://admin.example")
    request.url.path = "/api/client/widget/configuration"
    assert not middleware._is_origin_allowed(request, "https://admin.example")


def test_global_frontend_origin_can_use_client_chat_but_not_widget_routes():
    class CustomerOriginSession:
        def execute(self, *_args, **_kwargs):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(
                    all=lambda: [["https://customer.example"]]
                )
            )

        def close(self):
            pass

    middleware = DynamicCorsMiddleware(
        lambda scope, receive, send: None,
        settings=SimpleNamespace(
            cors_allow_local_origins=False,
            cors_allowed_origins=("https://admin.example/",),
        ),
        session_factory=CustomerOriginSession,
    )
    request = SimpleNamespace(
        headers={"X-API-Key": "application-key"},
        method="POST",
        url=SimpleNamespace(path="/api/client/chat/messages"),
    )

    assert middleware._is_origin_allowed(request, "https://admin.example")
    request.url.path = "/api/client/widget/configuration"
    assert not middleware._is_origin_allowed(request, "https://admin.example")
