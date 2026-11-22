from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import load_settings
from app.core.exceptions import ApplicationError
from app.infrastructure.providers.llm.nvidia_provider import NvidiaLlmProvider


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                "https://integrate.api.nvidia.com/v1/chat/completions",
            )
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "NVIDIA request failed",
                request=request,
                response=response,
            )

    def json(self):
        return self.payload


def _settings(**overrides):
    values = {
        "api_key": "nvapi-test-key",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "provider_timeout_seconds": 10,
        "temperature": 0.3,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_nvidia_llm_sends_openai_compatible_chat_request_and_maps_usage(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response(
            {
                "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {
                    "prompt_tokens": 13,
                    "completion_tokens": 5,
                    "total_tokens": 18,
                },
            }
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.nvidia_provider.httpx.post",
        fake_post,
    )
    result = NvidiaLlmProvider(settings=_settings()).generate(
        system_prompt="Be concise",
        user_prompt="Question",
        temperature=0.1,
    )

    assert captured["url"] == (
        "https://integrate.api.nvidia.com/v1/chat/completions"
    )
    assert captured["headers"]["Authorization"] == "Bearer nvapi-test-key"
    assert captured["json"] == {
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
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


def test_nvidia_llm_requires_api_key():
    with pytest.raises(ApplicationError) as error:
        NvidiaLlmProvider(settings=_settings(api_key="")).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "nvidia_api_key_missing"


def test_nvidia_llm_rate_limit_is_retryable(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return _Response({}, status_code=429)

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.nvidia_provider.httpx.post",
        fake_post,
    )
    with pytest.raises(ApplicationError) as error:
        NvidiaLlmProvider(settings=_settings()).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "nvidia_llm_request_failed"
    assert error.value.details == {"upstream_status": 429, "retryable": True}


def test_nvidia_application_model_is_used_by_runtime_provider(monkeypatch):
    from app.api.dependencies import _build_llm_provider

    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    settings = load_settings()
    provider = _build_llm_provider(
        settings,
        provider_name="nvidia",
        model_name="nvidia/nemotron-3.5-super-120b-a12b",
    )

    assert isinstance(provider, NvidiaLlmProvider)
    assert provider.settings.model == "nvidia/nemotron-3.5-super-120b-a12b"


def test_load_settings_reads_nvidia_provider_credentials_and_model(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "nvidia/nemotron-3.5-super-120b-a12b")

    settings = load_settings()

    assert settings.nvidia.api_key == "nvapi-test-key"
    assert settings.nvidia.base_url == "https://integrate.api.nvidia.com/v1"
    assert settings.nvidia.model == "nvidia/nemotron-3.5-super-120b-a12b"
