from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials
from fastapi.testclient import TestClient
import pytest

from app.api.dependencies import require_admin
from app.main import app


def test_admin_auth_fails_closed_when_environment_credentials_are_missing(monkeypatch):
    monkeypatch.delenv("ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)

    with pytest.raises(HTTPException) as error:
        require_admin(
            HTTPBasicCredentials(
                username="random-user",
                password="random-password",
            )
        )

    assert error.value.status_code == 503


def test_admin_auth_accepts_only_configured_credentials(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "configured-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "configured-password")

    with pytest.raises(HTTPException) as error:
        require_admin(
            HTTPBasicCredentials(
                username="random-user",
                password="random-password",
            )
        )

    assert error.value.status_code == 401
    assert require_admin(
        HTTPBasicCredentials(
            username="configured-admin",
            password="configured-password",
        )
    ) is None


def test_admin_routes_require_authentication(monkeypatch):
    monkeypatch.setenv("ADMIN_USERNAME", "configured-admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "configured-password")
    client = TestClient(app)

    for path in (
        "/api/admin/applications",
        "/api/admin/knowledge-bases",
        "/api/admin/settings/by-application/00000000-0000-0000-0000-000000000001",
    ):
        response = client.get(path)
        assert response.status_code == 401
