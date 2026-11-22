from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import load_settings
from app.core.exceptions import ApplicationError
from app.infrastructure.providers.llm.huggingface_provider import (
    HuggingFaceLlmProvider,
)


class _Response:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def _settings(**overrides):
    values = {
        "token": "hf-test-token",
        "llm_model": "Qwen/Qwen2.5-7B-Instruct-1M",
        "provider_timeout_seconds": 10,
        "llm_temperature": 0.4,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_huggingface_llm_posts_chat_and_maps_usage(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured.update(url=url, **kwargs)
        return _Response(
            {
                "model": "provider/model",
                "choices": [{"message": {"content": "Answer"}}],
                "usage": {
                    "prompt_tokens": 15,
                    "completion_tokens": 6,
                    "total_tokens": 21,
                },
            }
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.huggingface_provider.httpx.post",
        fake_post,
    )
    result = HuggingFaceLlmProvider(settings=_settings()).generate(
        system_prompt="Be concise",
        user_prompt="Question",
        temperature=0.1,
    )

    assert captured["url"] == "https://router.huggingface.co/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer hf-test-token"
    assert captured["json"] == {
        "model": "Qwen/Qwen2.5-7B-Instruct-1M",
        "messages": [
            {"role": "system", "content": "Be concise"},
            {"role": "user", "content": "Question"},
        ],
        "temperature": 0.1,
        "stream": False,
    }
    assert result.text == "Answer"
    assert result.model == "provider/model"
    assert result.input_tokens == 15
    assert result.output_tokens == 6
    assert result.total_tokens == 21


def test_huggingface_llm_requires_provider_token():
    with pytest.raises(ApplicationError) as error:
        HuggingFaceLlmProvider(settings=_settings(token="")).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "huggingface_token_missing"


def test_huggingface_llm_marks_rate_limit_as_retryable(monkeypatch):
    response = httpx.Response(
        429,
        request=httpx.Request("POST", "https://router.huggingface.co/v1/chat/completions"),
    )

    def fake_post(*_args, **_kwargs):
        raise httpx.HTTPStatusError(
            "rate limited",
            request=response.request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.huggingface_provider.httpx.post",
        fake_post,
    )
    with pytest.raises(ApplicationError) as error:
        HuggingFaceLlmProvider(settings=_settings()).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert error.value.code == "huggingface_llm_request_failed"
    assert error.value.details == {"upstream_status": 429, "retryable": True}


def test_huggingface_llm_is_constructed_with_application_model(monkeypatch):
    from app.api.dependencies import _build_llm_provider
    from app.infrastructure.providers.llm.huggingface_provider import (
        HuggingFaceLlmProvider,
    )

    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    settings = load_settings()
    provider = _build_llm_provider(
        settings,
        provider_name="huggingface",
        model_name="google/gemma-2-2b-it",
    )

    assert isinstance(provider, HuggingFaceLlmProvider)
    assert provider.settings.llm_model == "google/gemma-2-2b-it"
