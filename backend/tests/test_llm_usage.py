from types import SimpleNamespace

import httpx
import pytest

from app.core.exceptions import ApplicationError
from app.infrastructure.providers.llm.ollama_provider import OllamaLlmProvider
from app.infrastructure.providers.llm.openrouter_provider import OpenRouterLlmProvider


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def test_openrouter_provider_returns_normalized_usage(monkeypatch):
    captured = {}

    def fake_post(*_args, **kwargs):
        captured.update(kwargs)
        return _Response(
            {
                "model": "actual/chat-model",
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {
                    "prompt_tokens": 19,
                    "completion_tokens": 7,
                    "total_tokens": 26,
                },
            }
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openrouter_provider.httpx.post",
        fake_post,
    )
    provider = OpenRouterLlmProvider(
        settings=SimpleNamespace(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="configured/chat-model",
            temperature=0.2,
            provider_timeout_seconds=10,
        )
    )

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.text == "Answer"
    assert result.model == "actual/chat-model"
    assert result.input_tokens == 19
    assert result.output_tokens == 7
    assert result.total_tokens == 26
    assert result.latency_ms >= 0
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["model"] == "configured/chat-model"


def test_openrouter_does_not_fall_back_when_selected_model_is_unavailable(
    monkeypatch,
):
    attempted_models = []
    request = httpx.Request(
        "POST",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    response = httpx.Response(404, request=request)

    def fail_selected_model(_url, **kwargs):
        attempted_models.append(kwargs["json"]["model"])
        raise httpx.HTTPStatusError(
            "model unavailable",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openrouter_provider.httpx.post",
        fail_selected_model,
    )
    provider = OpenRouterLlmProvider(
        settings=SimpleNamespace(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="selected/model",
            temperature=0.2,
            provider_timeout_seconds=10,
        )
    )

    with pytest.raises(ApplicationError) as error:
        provider.generate(system_prompt="", user_prompt="question")

    assert error.value.code == "openrouter_provider_failed"
    assert error.value.details == {
        "upstream_status": 404,
        "model": "selected/model",
        "retryable": False,
    }
    assert attempted_models == ["selected/model"]


def test_openrouter_surfaces_provider_model_not_found_reason(monkeypatch):
    request = httpx.Request(
        "POST",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    response = httpx.Response(
        404,
        request=request,
        json={
            "error": {
                "message": "No endpoints found for qwen/qwen3-8b.",
                "code": 404,
            }
        },
    )

    def fail_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError(
            "model not found",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openrouter_provider.httpx.post",
        fail_request,
    )
    provider = OpenRouterLlmProvider(
        settings=SimpleNamespace(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="qwen/qwen3-8b",
            temperature=0.2,
            provider_timeout_seconds=10,
        )
    )

    with pytest.raises(ApplicationError) as error:
        provider.generate(system_prompt="", user_prompt="question")

    assert "No endpoints found for qwen/qwen3-8b" in error.value.message
    assert error.value.details["upstream_message"] == (
        "No endpoints found for qwen/qwen3-8b."
    )


def test_openrouter_429_surfaces_provider_rate_limit_details(monkeypatch):
    request = httpx.Request(
        "POST",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    response = httpx.Response(
        429,
        request=request,
        headers={"Retry-After": "30"},
        json={
            "error": {
                "message": "Provider returned error",
                "code": 429,
                "metadata": {
                    "provider_name": "Google",
                    "raw": "Rate limit exceeded",
                },
            }
        },
    )

    def fail_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError(
            "provider rate limited",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.openrouter_provider.httpx.post",
        fail_request,
    )
    provider = OpenRouterLlmProvider(
        settings=SimpleNamespace(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            model="google/gemma-4-26b-a4b-it:free",
            temperature=0.2,
            provider_timeout_seconds=10,
        )
    )

    with pytest.raises(ApplicationError) as error:
        provider.generate(system_prompt="", user_prompt="question")

    assert error.value.status_code == 503
    assert error.value.details == {
        "upstream_status": 429,
        "model": "google/gemma-4-26b-a4b-it:free",
        "retryable": True,
        "upstream_provider": "Google",
        "upstream_message": "Provider returned error",
        "upstream_detail": "Rate limit exceeded",
        "retry_after": "30",
    }
    assert "rate-limited" in error.value.message
    assert "Upstream provider: Google" in error.value.message
    assert "Rate limit exceeded" in error.value.message


def test_openrouter_default_catalog_contains_valid_qwen_chat_model(monkeypatch):
    from app.config.provider_registry import build_provider_catalog
    from app.config.settings import load_settings

    monkeypatch.delenv("OPENROUTER_MODELS", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    settings = load_settings()
    catalog = build_provider_catalog(settings)
    openrouter_models = {
        option.model for option in catalog.llms if option.provider == "openrouter"
    }

    assert "qwen/qwen3-vl-8b-instruct" in openrouter_models
    assert "qwen/qwen3-8b" not in openrouter_models


def test_llm_catalog_does_not_add_unlisted_default_model(monkeypatch):
    from app.config.provider_registry import build_provider_catalog
    from app.config.settings import load_settings

    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.setenv("OPENROUTER_MODEL", "qwen/qwen3-8b")
    monkeypatch.setenv("OPENROUTER_MODELS", "google/gemma-4-26b-a4b-it:free")

    catalog = build_provider_catalog(load_settings())

    assert {
        option.model for option in catalog.llms if option.provider == "openrouter"
    } == {"google/gemma-4-26b-a4b-it:free"}

    monkeypatch.delenv("OPENROUTER_MODELS")
    catalog_without_explicit_allowlist = build_provider_catalog(load_settings())

    assert "qwen/qwen3-8b" not in {
        option.model
        for option in catalog_without_explicit_allowlist.llms
        if option.provider == "openrouter"
    }


def test_ollama_http_error_identifies_selected_model(monkeypatch):
    request = httpx.Request("POST", "http://localhost:11434/api/chat")
    response = httpx.Response(404, request=request)

    def fail_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError(
            "model not installed",
            request=request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.ollama_provider.httpx.post",
        fail_request,
    )
    provider = OllamaLlmProvider(
        settings=SimpleNamespace(
            base_url="http://localhost:11434",
            llm_model_name="missing:latest",
            provider_timeout_seconds=10,
        )
    )

    with pytest.raises(ApplicationError) as error:
        provider.generate(system_prompt="", user_prompt="question")

    assert "missing:latest" in error.value.message
    assert error.value.details == {
        "upstream_status": 404,
        "model": "missing:latest",
        "retryable": False,
    }


def test_ollama_provider_maps_eval_counts_and_duration(monkeypatch):
    monkeypatch.setattr(
        "app.infrastructure.providers.llm.ollama_provider.httpx.post",
        lambda *_args, **_kwargs: _Response(
            {
                "model": "qwen2.5:7b",
                "message": {"content": "Answer"},
                "prompt_eval_count": 11,
                "eval_count": 5,
                "total_duration": 2_500_000_000,
            }
        ),
    )
    provider = OllamaLlmProvider(
        settings=SimpleNamespace(
            base_url="http://localhost:11434",
            llm_model_name="qwen2.5:7b",
            provider_timeout_seconds=10,
        )
    )

    result = provider.generate(system_prompt="system", user_prompt="question")

    assert result.text == "Answer"
    assert result.model == "qwen2.5:7b"
    assert result.input_tokens == 11
    assert result.output_tokens == 5
    assert result.total_tokens == 16
    assert result.latency_ms >= 0
    assert result.provider_duration_ms == 2500