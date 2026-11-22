from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import load_settings
from app.config.provider_registry import platform_default_selection
from app.core.exceptions import ApplicationError
from app.infrastructure.providers.llm.gemini_provider import GeminiLlmProvider


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                "https://generativelanguage.googleapis.com/v1beta/"
                "models/gemini-2.5-flash:generateContent",
            )
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "Gemini request failed",
                request=request,
                response=response,
            )

    def json(self):
        return self.payload


def _settings(**overrides):
    values = {
        "api_key": "gemini-test-key",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "model": "gemini-2.5-flash",
        "provider_timeout_seconds": 10,
        "temperature": 0.3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_gemini_llm_sends_generate_content_and_maps_usage(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response(
            {
                "modelVersion": "gemini-2.5-flash",
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "internal thought", "thought": True},
                                {"text": "Answer"},
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 13,
                    "candidatesTokenCount": 5,
                    "totalTokenCount": 18,
                },
            }
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.gemini_provider.httpx.post",
        fake_post,
    )
    result = GeminiLlmProvider(settings=_settings()).generate(
        system_prompt="Be concise",
        user_prompt="Question",
        temperature=0.1,
    )

    assert captured["url"] == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent"
    )
    assert captured["headers"]["x-goog-api-key"] == "gemini-test-key"
    assert captured["json"] == {
        "contents": [{"role": "user", "parts": [{"text": "Question"}]}],
        "generationConfig": {"temperature": 0.1},
        "systemInstruction": {"parts": [{"text": "Be concise"}]},
    }
    assert result.text == "Answer"
    assert result.model == "gemini-2.5-flash"
    assert result.input_tokens == 13
    assert result.output_tokens == 5
    assert result.total_tokens == 18


def test_gemini_llm_requires_api_key():
    with pytest.raises(ApplicationError) as error:
        GeminiLlmProvider(settings=_settings(api_key="")).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "gemini_api_key_missing"


def test_gemini_llm_rate_limit_is_retryable(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.providers.llm.gemini_provider.httpx.post",
        lambda *_args, **_kwargs: _Response({}, status_code=429),
    )

    with pytest.raises(ApplicationError) as error:
        GeminiLlmProvider(settings=_settings()).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "gemini_llm_request_failed"
    assert error.value.details == {
        "upstream_status": 429,
        "model": "gemini-2.5-flash",
        "retryable": True,
    }


def test_gemini_application_model_is_used_by_runtime_provider(monkeypatch):
    from app.api.dependencies import _build_llm_provider

    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    settings = load_settings()
    provider = _build_llm_provider(
        settings,
        provider_name="gemini",
        model_name="gemini-2.5-pro",
    )

    assert isinstance(provider, GeminiLlmProvider)
    assert provider.settings.model == "gemini-2.5-pro"


def test_load_settings_reads_gemini_configuration(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test-key")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-pro")
    monkeypatch.setenv("GEMINI_MODELS", "gemini-2.5-pro, gemini-custom")
    monkeypatch.setenv("GEMINI_TEMPERATURE", "0.4")

    settings = load_settings()

    assert settings.gemini.api_key == "gemini-test-key"
    assert settings.gemini.base_url == (
        "https://generativelanguage.googleapis.com/v1beta"
    )
    assert settings.gemini.model == "gemini-2.5-pro"
    assert settings.gemini.temperature == 0.4
    assert settings.gemini.models == ("gemini-2.5-pro", "gemini-custom")
    assert platform_default_selection(settings, capability="llm") == (
        "gemini",
        "gemini-2.5-pro",
    )
