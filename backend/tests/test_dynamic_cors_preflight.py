from fastapi.testclient import TestClient

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
