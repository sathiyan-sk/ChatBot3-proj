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
        "llm_inference_provider": "featherless-ai",
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
        "model": "Qwen/Qwen2.5-7B-Instruct-1M:featherless-ai",
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


def test_huggingface_llm_preserves_explicit_provider_suffix(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        "app.infrastructure.providers.llm.huggingface_provider.httpx.post",
        lambda _url, **kwargs: (
            captured.update(kwargs) or _Response(
                {"choices": [{"message": {"content": "Answer"}}]}
            )
        ),
    )

    HuggingFaceLlmProvider(
        settings=_settings(llm_model="Qwen/Qwen2.5-7B-Instruct:novita")
    ).generate(system_prompt="", user_prompt="Question")

    assert captured["json"]["model"] == "Qwen/Qwen2.5-7B-Instruct:novita"


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
    assert error.value.details == {
        "upstream_status": 429,
        "model": "Qwen/Qwen2.5-7B-Instruct-1M",
        "inference_provider": "featherless-ai",
        "retryable": True,
    }


def test_huggingface_llm_reports_selected_model_and_provider_on_http_error(
    monkeypatch,
):
    response = httpx.Response(
        400,
        request=httpx.Request(
            "POST",
            "https://router.huggingface.co/v1/chat/completions",
        ),
    )

    def fail_request(*_args, **_kwargs):
        raise httpx.HTTPStatusError(
            "bad request",
            request=response.request,
            response=response,
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.llm.huggingface_provider.httpx.post",
        fail_request,
    )
    with pytest.raises(ApplicationError) as error:
        HuggingFaceLlmProvider(settings=_settings()).generate(
            system_prompt="",
            user_prompt="Question",
        )

    assert "Qwen/Qwen2.5-7B-Instruct-1M" in error.value.message
    assert "featherless-ai" in error.value.message


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
    assert provider.settings.llm_inference_provider == "featherless-ai"


def test_load_settings_reads_huggingface_chat_provider(monkeypatch):
    monkeypatch.setenv("HF_LLM_INFERENCE_PROVIDER", "novita")

    settings = load_settings()

    assert settings.huggingface.llm_inference_provider == "novita"
