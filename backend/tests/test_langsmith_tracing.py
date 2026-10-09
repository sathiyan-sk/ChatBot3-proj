from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

import langsmith

from app.infrastructure.observability.logging import (
    reset_request_id,
    set_request_id,
)
from app.infrastructure.observability.tracing import (
    LangSmithTraceObserver,
    NoOpTraceObserver,
    TraceContext,
    TraceRunType,
    TracedLlmProvider,
)
from app.knowledge_engine.contracts.embeddings import EmbeddingsContract
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.domain.provider_interfaces import LlmProvider
from app.knowledge_engine.generation.citation_builder import CitationBuilder
from app.knowledge_engine.generation.prompt_builder import PromptBuilder
from app.knowledge_engine.generation.response_formatter import ResponseFormatter
from app.knowledge_engine.generation.response_generator import ResponseGenerator
from app.knowledge_engine.pipelines.question_answering_pipeline import (
    QuestionAnsweringPipeline,
)
from app.knowledge_engine.retrieval.conversation_context_builder import (
    ConversationContextBuilder,
)
from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.query_embedder import QueryEmbedder
from app.knowledge_engine.retrieval.reranker import Reranker
from app.knowledge_engine.shared.models import RetrievedChunk
from app.knowledge_engine.shared.models import (
    QuestionAnsweringPipelineRequest,
)


class _FakeRun:
    def __init__(self) -> None:
        self.outputs = None
        self.error = None

    def end(self, *, outputs=None, error=None) -> None:
        self.outputs = outputs
        self.error = error


class _FakeClient:
    def __init__(self, **kwargs: Any) -> None:
        self.options = kwargs
        self.flushed = False

    def flush(self, timeout: float | None = None) -> None:
        _ = timeout
        self.flushed = True


class _FakeEmbeddings(EmbeddingsContract):
    def embed_query(self, text: str) -> list[float]:
        _ = text
        return [0.0]


class _EmptyVectorStore(VectorStoreContract):
    def index_chunk(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        _ = (chunk_id, content, embedding, metadata)
        raise NotImplementedError

    def similarity_search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        _ = (knowledge_base_id, query_embedding, top_k)
        return []

    def keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        _ = (knowledge_base_id, query_text, top_k)
        return []


class _UnusedLlmProvider(LlmProvider):
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> LlmGenerationResult:
        _ = (system_prompt, user_prompt, temperature)
        raise AssertionError("The no-retrieval path must not call the LLM.")


class _RecordingObserver(NoOpTraceObserver):
    def __init__(self) -> None:
        self.run = _FakeRun()
        self.options: dict[str, Any] = {}

    @contextmanager
    def trace(
        self,
        *,
        name: str,
        run_type: TraceRunType = "chain",
        inputs: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> Generator[TraceContext, None, None]:
        self.options = {
            "name": name,
            "run_type": run_type,
            "inputs": inputs,
            "metadata": metadata,
            "request_id": request_id,
        }
        yield TraceContext(request_id=request_id or "", _run=self.run)


def test_langsmith_observer_records_run_outputs_and_request_id(monkeypatch):
    traces = []
    runs = []
    clients = []

    def fake_client(**kwargs: Any):
        client = _FakeClient(**kwargs)
        clients.append(client)
        return client

    @contextmanager
    def fake_tracing_context(**kwargs: Any) -> Generator[dict[str, Any], None, None]:
        yield kwargs

    @contextmanager
    def fake_trace(**kwargs: Any) -> Generator[_FakeRun, None, None]:
        run = _FakeRun()
        traces.append(kwargs)
        runs.append(run)
        yield run

    monkeypatch.setattr(langsmith, "Client", fake_client)
    monkeypatch.setattr(langsmith, "tracing_context", fake_tracing_context)
    monkeypatch.setattr(langsmith, "trace", fake_trace)

    observer = LangSmithTraceObserver(
        enabled=True,
        api_key="test-api-key",
        project="support-prod",
        endpoint="https://smith.example",
    )
    with observer.trace(
        name="question_answering_pipeline",
        run_type="chain",
        inputs={"query": "How do I update my plan?"},
        request_id="request-123",
    ) as run_context:
        run_context.end(outputs={"answer": "Use account settings."})

    observer.flush()

    assert clients[0].options == {
        "api_key": "test-api-key",
        "api_url": "https://smith.example",
    }
    assert traces[0]["run_type"] == "chain"
    assert traces[0]["metadata"]["request_id"] == "request-123"
    assert runs[0].outputs == {"answer": "Use account settings."}
    assert clients[0].flushed


def test_traced_llm_provider_records_normalized_usage_and_request_id():
    result = LlmGenerationResult(
        text="Answer",
        model="test-model",
        input_tokens=12,
        output_tokens=5,
        total_tokens=17,
        latency_ms=125.0,
        provider_duration_ms=100.0,
    )
    captured = {}

    class Provider(LlmProvider):
        def generate(
            self,
            *,
            system_prompt: str,
            user_prompt: str,
            temperature: float | None = None,
        ) -> LlmGenerationResult:
            captured["provider_kwargs"] = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "temperature": temperature,
            }
            return result

    class Observer(NoOpTraceObserver):
        @contextmanager
        def trace(
            self,
            *,
            name: str,
            run_type: TraceRunType = "chain",
            inputs: dict[str, Any] | None = None,
            metadata: dict[str, Any] | None = None,
            request_id: str | None = None,
        ) -> Generator[TraceContext, None, None]:
            kwargs = {
                "name": name,
                "run_type": run_type,
                "inputs": inputs,
                "metadata": metadata,
                "request_id": request_id,
            }
            captured["trace_kwargs"] = kwargs
            run = _FakeRun()
            yield TraceContext(request_id=kwargs.get("request_id") or "", _run=run)
            captured["outputs"] = run.outputs

    request_id_token = set_request_id("request-456")
    try:
        traced_provider = TracedLlmProvider(
            provider=Provider(),
            trace_observer=Observer(),
        )
        actual = traced_provider.generate(
            system_prompt="system",
            user_prompt="question",
            temperature=0.4,
        )
    finally:
        reset_request_id(request_id_token)

    assert actual is result
    assert captured["trace_kwargs"]["run_type"] == "llm"
    assert captured["trace_kwargs"]["request_id"] == "request-456"
    assert captured["outputs"] == {
        "answer": "Answer",
        "model": "test-model",
        "usage": {
            "input_tokens": 12,
            "output_tokens": 5,
            "total_tokens": 17,
        },
        "latency_ms": 125.0,
        "provider_duration_ms": 100.0,
    }


def test_qa_pipeline_finishes_parent_trace_for_no_retrieval():
    observer = _RecordingObserver()
    pipeline = QuestionAnsweringPipeline(
        conversation_context_builder=ConversationContextBuilder(),
        query_embedder=QueryEmbedder(_FakeEmbeddings()),
        hybrid_retriever=HybridRetriever(_EmptyVectorStore()),
        metadata_filter=MetadataFilter(),
        reranker=Reranker(),
        prompt_builder=PromptBuilder(),
        response_generator=ResponseGenerator(_UnusedLlmProvider()),
        citation_builder=CitationBuilder(),
        response_formatter=ResponseFormatter(),
        trace_observer=observer,
    )

    result = pipeline.run(
        QuestionAnsweringPipelineRequest(
            application_id="app-1",
            knowledge_base_id="kb-1",
            query_text="Unmatched question",
            conversation_id="conversation-1",
            messages=[],
            request_id="request-789",
        )
    )

    assert result.answer_text
    assert observer.options["run_type"] == "chain"
    assert isinstance(observer.options["metadata"], dict)
    assert observer.options["metadata"]["request_id"] == "request-789"
    assert observer.run.outputs is not None
    assert observer.run.outputs["retrieved_chunk_count"] == 0
    assert observer.run.outputs["answer"] == result.answer_text
