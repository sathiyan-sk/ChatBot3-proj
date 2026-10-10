from types import SimpleNamespace

import pytest

from app.config.settings import HuggingFaceSettings, load_settings
from app.core.exceptions import ApplicationError, ConfigurationError
from app.infrastructure.providers.embeddings.factory import build_embeddings_provider
from app.infrastructure.providers.embeddings.huggingface_embeddings_provider import (
    HuggingFaceEmbeddingsProvider,
)


def _settings(*, batch_size: int = 2) -> HuggingFaceSettings:
    return HuggingFaceSettings(
        token="hf-test-token",
        embedding_model="BAAI/bge-large-en-v1.5",
        inference_provider="hf-inference",
        provider_timeout_seconds=10,
        embedding_batch_size=batch_size,
    )


def test_huggingface_embeddings_batch_and_validate_dimensions(monkeypatch):
    requests = []

    class FakeResponse:
        def __init__(self, values):
            self.values = values

        def tolist(self):
            return self.values

    class FakeClient:
        def __init__(self, **kwargs):
            assert kwargs == {
                "model": "BAAI/bge-large-en-v1.5",
                "provider": "hf-inference",
                "token": "hf-test-token",
                "timeout": 10,
            }

        def feature_extraction(self, texts):
            requests.append(texts)
            return FakeResponse(
                [[float(index)] * 3 for index in range(len(texts))]
            )

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.huggingface_embeddings_provider.InferenceClient",
        FakeClient,
    )
    provider = HuggingFaceEmbeddingsProvider(
        settings=_settings(),
        vector_dimension=3,
    )

    vectors = provider.embed_documents(["one", "two", "three"])

    assert requests == [["one", "two"], ["three"]]
    assert vectors == [
        [0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
    ]


def test_huggingface_embeddings_reject_dimension_mismatch(monkeypatch):
    class FakeResponse:
        def tolist(self):
            return [[0.1, 0.2]]

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        def feature_extraction(self, _texts):
            return FakeResponse()

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.huggingface_embeddings_provider.InferenceClient",
        FakeClient,
    )
    provider = HuggingFaceEmbeddingsProvider(
        settings=_settings(),
        vector_dimension=3,
    )

    with pytest.raises(ApplicationError) as error:
        provider.embed_query("text")

    assert error.value.code == "huggingface_embedding_dimension_mismatch"


def test_huggingface_embeddings_require_token():
    settings = HuggingFaceSettings(
        token="",
        embedding_model="BAAI/bge-large-en-v1.5",
        inference_provider="hf-inference",
        provider_timeout_seconds=10,
        embedding_batch_size=2,
    )

    with pytest.raises(ApplicationError) as error:
        HuggingFaceEmbeddingsProvider(settings=settings, vector_dimension=1024)

    assert error.value.code == "huggingface_token_missing"


def test_load_settings_configures_huggingface_embedding_provider(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "huggingface")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    monkeypatch.setenv("HF_EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")
    monkeypatch.setenv("HF_INFERENCE_PROVIDER", "hf-inference")

    settings = load_settings()
    provider = build_embeddings_provider(settings)

    assert isinstance(provider, HuggingFaceEmbeddingsProvider)
    assert settings.providers.llm == "openrouter"
    assert settings.vector_store_dimension == 1024


def test_openai_embedding_provider_uses_configured_model_and_dimensions(monkeypatch):
    from app.config.settings import OpenAIEmbeddingsSettings
    from app.infrastructure.providers.embeddings.openai_embeddings_provider import (
        OpenAIEmbeddingsProvider,
    )

    requests = []

    class FakeResponse:
        def __init__(self, values):
            self.values = values

        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {"index": index, "embedding": vector}
                    for index, vector in self.values
                ]
            }

    def fake_post(url, *, json, headers, timeout):
        requests.append((url, json, headers, timeout))
        batch = json["input"]
        return FakeResponse(
            [
                (index, [float(index)] * 3)
                for index in reversed(range(len(batch)))
            ]
        )

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.openai_embeddings_provider.httpx.post",
        fake_post,
    )
    provider = OpenAIEmbeddingsProvider(
        settings=OpenAIEmbeddingsSettings(
            base_url="https://api.openai.com/v1",
            api_key="test-openai-key",
            embedding_model="text-embedding-3-small",
            embedding_dimensions=3,
            provider_timeout_seconds=10,
            embedding_batch_size=2,
        ),
        vector_dimension=3,
    )

    vectors = provider.embed_documents(["one", "two", "three"])

    assert [request[1]["model"] for request in requests] == [
        "text-embedding-3-small",
        "text-embedding-3-small",
    ]
    assert [request[1]["dimensions"] for request in requests] == [3, 3]
    assert [request[1]["input"] for request in requests] == [
        ["one", "two"],
        ["three"],
    ]
    assert vectors == [
        [0.0, 0.0, 0.0],
        [1.0, 1.0, 1.0],
        [0.0, 0.0, 0.0],
    ]


def test_openai_provider_rejects_vector_dimension_mismatch():
    from app.config.settings import OpenAIEmbeddingsSettings
    from app.infrastructure.providers.embeddings.openai_embeddings_provider import (
        OpenAIEmbeddingsProvider,
    )

    with pytest.raises(ApplicationError) as error:
        OpenAIEmbeddingsProvider(
            settings=OpenAIEmbeddingsSettings(
                base_url="https://api.openai.com/v1",
                api_key="test-openai-key",
                embedding_model="text-embedding-3-small",
                embedding_dimensions=1536,
                provider_timeout_seconds=10,
                embedding_batch_size=32,
            ),
            vector_dimension=1024,
        )

    assert error.value.code == "openai_embedding_dimension_configuration_mismatch"


def test_openai_can_be_selected_without_changing_llm_provider(monkeypatch):
    from app.infrastructure.providers.embeddings.openai_embeddings_provider import (
        OpenAIEmbeddingsProvider,
    )

    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai-key")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")
    settings = load_settings()

    provider = build_embeddings_provider(settings)

    assert isinstance(provider, OpenAIEmbeddingsProvider)
    assert provider.settings.embedding_model == "text-embedding-3-small"
    assert settings.providers.llm == "openrouter"
    assert settings.vector_store_dimension == 1024


def test_embedding_provider_factory_rejects_unknown_provider():
    settings = SimpleNamespace(
        providers=SimpleNamespace(embeddings="unknown"),
    )

    with pytest.raises(ConfigurationError, match="Unsupported EMBEDDING_PROVIDER"):
        build_embeddings_provider(settings)
