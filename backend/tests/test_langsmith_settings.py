import pytest

from app.config.settings import load_settings


def test_langsmith_tracing_defaults_disabled_without_credentials(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    monkeypatch.delenv("LANGSMITH_ENDPOINT", raising=False)

    settings = load_settings()

    assert settings.langsmith_tracing is False
    assert settings.langsmith_api_key is None
    assert settings.langsmith_project is None
    assert settings.langsmith_endpoint is None


@pytest.mark.parametrize(
    ("api_key", "project", "missing"),
    [
        (None, "rag-prod", "LANGSMITH_API_KEY"),
        ("test-key", None, "LANGSMITH_PROJECT"),
    ],
)
def test_langsmith_tracing_requires_api_key_and_project(
    monkeypatch,
    api_key,
    project,
    missing,
):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    if api_key is None:
        monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    else:
        monkeypatch.setenv("LANGSMITH_API_KEY", api_key)
    if project is None:
        monkeypatch.delenv("LANGSMITH_PROJECT", raising=False)
    else:
        monkeypatch.setenv("LANGSMITH_PROJECT", project)

    with pytest.raises(ValueError, match=missing):
        load_settings()


def test_langsmith_tracing_loads_configuration_when_enabled(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "test-key")
    monkeypatch.setenv("LANGSMITH_PROJECT", "rag-prod")
    monkeypatch.setenv("LANGSMITH_ENDPOINT", "https://langsmith.example")

    settings = load_settings()

    assert settings.langsmith_tracing is True
    assert settings.langsmith_api_key == "test-key"
    assert settings.langsmith_project == "rag-prod"
    assert settings.langsmith_endpoint == "https://langsmith.example"