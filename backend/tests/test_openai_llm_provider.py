from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import load_settings
from app.config.provider_registry import platform_default_selection
from app.core.exceptions import ApplicationError, ConfigurationError
from app.infrastructure.providers.llm.openai_provider import OpenAILlmProvider


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "OpenAI request failed",
                request=request,
                response=response,
            )

    def json(self):
        return self.payload


def _settings(**overrides):
    values = {
        "api_key": "openai-test-key",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
        "provider_timeout_seconds": 10,
        "temperature": 0.3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_openai_llm_sends_chat_request_and_maps_usage(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response(
            {
                "model": "gpt-4.1-mini",
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {
                    "prompt_tokens": 13,
                    "completion_tokens": 5,
                    "total_tokens": 18,
                },
            }
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openai_provider.httpx.post",
        fake_post,
    )
    result = OpenAILlmProvider(settings=_settings()).generate(
        system_prompt="Be concise",
        user_prompt="Question",
        temperature=0.1,
    )

    assert captured["url"] == "https://api.openai.com/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer openai-test-key"
    assert captured["json"] == {
        "model": "gpt-4.1-mini",
        "messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Question"},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    assert result.text == "Answer"
    assert result.input_tokens == 13
    assert result.output_tokens == 5
    assert result.total_tokens == 18


def test_openai_llm_requires_api_key():
    with pytest.raises(ApplicationError) as error:
        OpenAILlmProvider(settings=_settings(api_key="")).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "openai_api_key_missing"


def test_openai_llm_rate_limit_is_retryable(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openai_provider.httpx.post",
        lambda *_args, **_kwargs: _Response({}, status_code=429),
    )

    with pytest.raises(ApplicationError) as error:
        OpenAILlmProvider(settings=_settings()).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "openai_llm_request_failed"
    assert error.value.details == {
        "upstream_status": 429,
        "model": "gpt-4.1-mini",
        "retryable": True,
    }


def test_openai_application_model_is_used_by_runtime_provider(monkeypatch):
    from app.api.dependencies import _build_llm_provider

    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    settings = load_settings()
    provider = _build_llm_provider(
        settings,
        provider_name="openai",
        model_name="gpt-4.1",
    )

    assert isinstance(provider, OpenAILlmProvider)
    assert provider.settings.model == "gpt-4.1"


def test_runtime_rejects_openai_model_outside_backend_allowlist(monkeypatch):
    from app.api.dependencies import _build_llm_provider

    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_LLM_MODELS", "gpt-4.1-mini")
    settings = load_settings()

    with pytest.raises(ConfigurationError):
        _build_llm_provider(
            settings,
            provider_name="openai",
            model_name="not-in-the-platform-allowlist",
        )


def test_load_settings_reads_openai_llm_configuration(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("OPENAI_LLM_MODEL", "gpt-4.1")
    monkeypatch.setenv("OPENAI_LLM_MODELS", "gpt-4.1, custom-model, gpt-4.1")
    monkeypatch.setenv("OPENAI_LLM_TEMPERATURE", "0.4")

    settings = load_settings()

    assert settings.openai_llm.api_key == "openai-test-key"
    assert settings.openai_llm.base_url == "https://api.openai.com/v1"
    assert settings.openai_llm.model == "gpt-4.1"
    assert settings.openai_llm.temperature == 0.4
    assert settings.openai_llm.models == ("gpt-4.1", "custom-model")
    assert platform_default_selection(settings, capability="llm") == (
        "openai",
        "gpt-4.1",
    )
