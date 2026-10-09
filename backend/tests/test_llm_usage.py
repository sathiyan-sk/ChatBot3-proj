from types import SimpleNamespace

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