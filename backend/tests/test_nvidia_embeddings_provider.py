from dataclasses import replace
from types import SimpleNamespace

import httpx
import pytest

from app.config.settings import load_settings
from app.config.provider_registry import build_provider_catalog
from app.core.exceptions import ApplicationError, ConfigurationError
from app.infrastructure.providers.embeddings.factory import build_embeddings_provider
from app.infrastructure.providers.embeddings.nvidia_embeddings_provider import (
    NvidiaEmbeddingsProvider,
)


def _settings(**overrides):
    values = {
        "api_key": "nvapi-test-key",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "nvidia/nemotron-3.5-lightning-30b-a3b",
        "provider_timeout_seconds": 10,
        "embedding_model": "nvidia/nv-embedqa-e5-v5",
        "embedding_batch_size": 2,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class _Response:
    def __init__(self, payload, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            request = httpx.Request(
                "POST",
                "https://integrate.api.nvidia.com/v1/embeddings",
            )
            response = httpx.Response(self.status_code, request=request)
            raise httpx.HTTPStatusError(
                "NVIDIA request failed",
                request=request,
                response=response,
            )

    def json(self):
        return self.payload


def _provider(monkeypatch, fake_post):
    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.nvidia_embeddings_provider.httpx.post",
        fake_post,
    )
    return NvidiaEmbeddingsProvider(
        settings=_settings(),
        model_name="nvidia/nv-embedqa-e5-v5",
        vector_dimension=1024,
    )


def test_nvidia_embeddings_batch_documents_and_use_query_input_type(monkeypatch):
    requests = []

    def fake_post(url, *, json, headers, timeout):
        requests.append((url, json, headers, timeout))
        return _Response(
            {
                "data": [
                    {
                        "index": index,
                        "embedding": [float(index)] * 1024,
                    }
                    for index in reversed(range(len(json["input"])))
                ]
            }
        )

    provider = _provider(monkeypatch, fake_post)
    vectors = provider.embed_documents(["first", "second", "third"])
    query_vector = provider.embed_query("a question")

    assert [len(request[1]["input"]) for request in requests] == [2, 1, 1]
    assert [request[1]["input_type"] for request in requests] == [
        "passage",
        "passage",
        "query",
    ]
    assert all(request[1]["truncate"] == "END" for request in requests)
    assert requests[0][0] == "https://integrate.api.nvidia.com/v1/embeddings"
    assert requests[0][1]["model"] == "nvidia/nv-embedqa-e5-v5"
    assert requests[0][2]["Authorization"] == "Bearer nvapi-test-key"
    assert vectors == [[0.0] * 1024, [1.0] * 1024, [0.0] * 1024]
    assert query_vector == [0.0] * 1024


def test_nvidia_embeddings_reject_wrong_dimension():
    with pytest.raises(ConfigurationError, match="1024 dimensions"):
        NvidiaEmbeddingsProvider(
            settings=_settings(),
            model_name="nvidia/nv-embedqa-e5-v5",
            vector_dimension=768,
        )


def test_nvidia_embeddings_reject_unknown_model():
    with pytest.raises(ConfigurationError, match="Unsupported NVIDIA embedding model"):
        NvidiaEmbeddingsProvider(
            settings=_settings(),
            model_name="nvidia/nemotron-3-embed-1b",
            vector_dimension=1024,
        )


def test_nvidia_embeddings_reject_wrong_provider_output_dimension(monkeypatch):
    provider = _provider(
        monkeypatch,
        lambda *_args, **_kwargs: _Response(
            {"data": [{"embedding": [0.1] * 768}]}
        ),
    )
    with pytest.raises(ApplicationError) as error:
        provider.embed_query("a question")

    assert error.value.code == "nvidia_embedding_dimension_mismatch"


def test_nvidia_embeddings_catalog_requires_key_and_1024_dimension(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-test-key")
    settings = load_settings()
    provider = build_embeddings_provider(
        settings,
        provider_name="nvidia",
        model_name="nvidia/nv-embedqa-e5-v5",
    )
    assert isinstance(provider, NvidiaEmbeddingsProvider)
    catalog = build_provider_catalog(settings)
    assert any(
        option.provider == "nvidia"
        and option.model == "nvidia/nv-embedqa-e5-v5"
        and option.embedding_dimensions == 1024
        for option in catalog.embeddings
    )

    missing_key_settings = replace(
        settings,
        nvidia=replace(settings.nvidia, api_key=""),
    )
    assert not any(
        option.provider == "nvidia" for option in build_provider_catalog(missing_key_settings).embeddings
    )
    with pytest.raises(ApplicationError) as error:
        build_embeddings_provider(
            missing_key_settings,
            provider_name="nvidia",
            model_name="nvidia/nv-embedqa-e5-v5",
        )
    assert error.value.code == "nvidia_embedding_api_key_missing"

    incompatible_dimension_settings = replace(
        settings,
        vector_store_dimension=768,
    )
    assert not any(
        option.provider == "nvidia"
        for option in build_provider_catalog(incompatible_dimension_settings).embeddings
    )
