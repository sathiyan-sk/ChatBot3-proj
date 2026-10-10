from types import SimpleNamespace
import time

import httpx
import pytest

from app.core.exceptions import ApplicationError
from app.infrastructure.providers.embeddings.openrouter_embeddings_provider import (
    OpenRouterEmbeddingsProvider,
)
from app.knowledge_engine.ingestion.embedding_generator import EmbeddingGenerator
from app.knowledge_engine.shared.models import DocumentChunk


def _provider():
    return OpenRouterEmbeddingsProvider(
        settings=SimpleNamespace(
            api_key="test-key",
            base_url="https://openrouter.ai/api/v1",
            embedding_model="test-embedding-model",
            embedding_dimensions=2,
            provider_timeout_seconds=10,
        )
    )


def test_openrouter_batches_inputs_and_restores_response_order(monkeypatch):
    batches = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            batch = batches[-1]
            return {
                "data": [
                    {
                        "index": index,
                        "embedding": [float(index), float(index + 1)],
                    }
                    for index in reversed(range(len(batch)))
                ]
            }

    def fake_post(_url, *, json, headers, timeout):
        batches.append(json["input"])
        return Response()

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.openrouter_embeddings_provider.httpx.post",
        fake_post,
    )

    vectors = _provider().embed_documents(
        ["first", "second", "third"],
        batch_size=2,
    )

    assert batches == [["first", "second"], ["third"]]
    assert vectors == [[0.0, 1.0], [1.0, 2.0], [0.0, 1.0]]


def test_openrouter_uses_configured_batch_size_for_large_documents(monkeypatch):
    batches = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "data": [
                    {"index": index, "embedding": [1.0, 2.0]}
                    for index in range(len(batches[-1]))
                ]
            }

    def fake_post(_url, *, json, headers, timeout):
        batches.append(json["input"])
        return Response()

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.openrouter_embeddings_provider.httpx.post",
        fake_post,
    )

    provider = _provider()
    provider.settings.embedding_batch_size = 64
    vectors = provider.embed_documents([f"text-{index}" for index in range(129)])

    assert [len(batch) for batch in batches] == [64, 64, 1]
    assert len(vectors) == 129


def test_openrouter_retries_transient_read_timeout(monkeypatch):
    attempts = 0

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}

    def fake_post(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ReadTimeout("temporary timeout")
        return Response()

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.openrouter_embeddings_provider.httpx.post",
        fake_post,
    )
    monkeypatch.setattr(
        time,
        "sleep",
        lambda _seconds: None,
    )

    assert _provider().embed_query("some text") == [0.1, 0.2]
    assert attempts == 2


def test_openrouter_402_returns_actionable_billing_error_without_retry(monkeypatch):
    attempts = 0

    def fake_post(*_args, **_kwargs):
        nonlocal attempts
        attempts += 1
        request = httpx.Request(
            "POST",
            "https://openrouter.ai/api/v1/embeddings",
        )
        response = httpx.Response(402, request=request)
        response.raise_for_status()

    monkeypatch.setattr(
        "app.infrastructure.providers.embeddings.openrouter_embeddings_provider.httpx.post",
        fake_post,
    )

    with pytest.raises(ApplicationError) as error:
        _provider().embed_query("some text")

    assert attempts == 1
    assert error.value.code == "embedding_provider_payment_required"
    assert error.value.details == {"upstream_status": 402}
    assert "credits" in error.value.message
    assert "configured embedding model" in error.value.message


def test_embedding_generator_uses_batch_api_and_preserves_chunk_metadata():
    chunks = [
        DocumentChunk(
            chunk_id="chunk-a",
            content="alpha",
            metadata={"document_id": "doc-1"},
        ),
        DocumentChunk(
            chunk_id="chunk-b",
            content="beta",
            metadata={"document_id": "doc-1"},
        ),
    ]

    class BatchProvider:
        def embed_documents(self, texts):
            assert texts == ["alpha", "beta"]
            return [[1.0], [2.0]]

        def embed_query(self, _text):
            raise AssertionError("the batch API should be used")

    embedded = EmbeddingGenerator(BatchProvider()).generate(chunks)

    assert [chunk.chunk_id for chunk in embedded] == ["chunk-a", "chunk-b"]
    assert [chunk.embedding for chunk in embedded] == [[1.0], [2.0]]
    assert embedded[0].metadata == {"document_id": "doc-1"}