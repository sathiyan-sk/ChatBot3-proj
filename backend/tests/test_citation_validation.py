"""Citation validation: citations must be grounded to retrieved context only.

Asserts the structural guarantee that prevents fabricated references: every
emitted citation maps to a chunk that survived into the final context, citation
keys are unique, and the citation list is empty exactly when no evidence was
retrieved.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider
from app.knowledge_engine.generation.citation_builder import CitationBuilder
from app.knowledge_engine.generation.prompt_builder import PromptBuilder
from app.knowledge_engine.generation.response_formatter import ResponseFormatter
from app.knowledge_engine.generation.response_generator import ResponseGenerator
from app.knowledge_engine.pipelines.question_answering_pipeline import (
    QuestionAnsweringPipeline,
    QuestionAnsweringPipelineRequest,
)
from app.knowledge_engine.retrieval.context_builder import ContextBuilder
from app.knowledge_engine.retrieval.conversation_context_builder import (
    ConversationContextBuilder,
)
from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.query_embedder import QueryEmbedder
from app.knowledge_engine.retrieval.reranker import Reranker
from app.knowledge_engine.shared.models import RetrievedChunk
from app.infrastructure.observability.tracing import NoOpTraceObserver
from tests._retrieval_harness import CORPUS, E_PAYMENT, LookupEmbeddings


class _StubLlm(LlmProvider):
    """Deterministic LLM: returns a fixed answer regardless of the prompt."""

    def __init__(self, text: str = "I can help with questions about our business.") -> None:
        self._text = text

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> LlmGenerationResult:
        _ = (system_prompt, user_prompt, temperature)
        return LlmGenerationResult(
            text=self._text,
            model="stub",
            input_tokens=1,
            output_tokens=1,
            total_tokens=2,
            latency_ms=0.0,
        )


def _build_pipeline(store) -> QuestionAnsweringPipeline:
    return QuestionAnsweringPipeline(
        conversation_context_builder=ConversationContextBuilder(),
        query_embedder=QueryEmbedder(LookupEmbeddings({"What payment methods are accepted?": E_PAYMENT})),
        hybrid_retriever=HybridRetriever(store),
        metadata_filter=MetadataFilter(),
        reranker=Reranker(),
        context_builder=ContextBuilder(),
        prompt_builder=PromptBuilder(),
        response_generator=ResponseGenerator(_StubLlm()),
        citation_builder=CitationBuilder(),
        response_formatter=ResponseFormatter(),
        trace_observer=NoOpTraceObserver(),
    )


def _chunk(chunk_id: str, content: str, document_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title="Doc",
        content=content,
        score=score,
        source_uri=None,
        metadata={},
    )


def test_citation_builder_emits_one_per_distinct_context_chunk() -> None:
    chunks = [
        _chunk("c1", "alpha evidence", "doc_a", score=0.9),
        _chunk("c2", "beta evidence", "doc_b", score=0.8),
        _chunk("c1", "alpha evidence", "doc_a", score=0.9),  # duplicate chunk_id
    ]
    citations = CitationBuilder().build(chunks)

    assert len(citations) == 2
    keys = {(c.document_id, c.chunk_id) for c in citations}
    assert len(keys) == 2
    # No fabricated reference: every citation must map to a supplied chunk.
    supplied = {(c.document_id, c.chunk_id) for c in chunks}
    for citation in citations:
        assert (citation.document_id, citation.chunk_id) in supplied


def test_citations_empty_when_context_empty() -> None:
    assert CitationBuilder().build([]) == []


def test_pipeline_citations_ground_to_retrieved_chunks() -> None:
    from tests._retrieval_harness import DeterministicVectorStore

    pipeline = _build_pipeline(DeterministicVectorStore(CORPUS))
    result = pipeline.run(
        QuestionAnsweringPipelineRequest(
            application_id="app-1",
            knowledge_base_id="kb-1",
            query_text="What payment methods are accepted?",
            conversation_id="conversation-1",
            messages=[],
            top_k=5,
            request_id="request-cite-1",
        )
    )

    # There is supporting evidence for this query, so the pipeline must cite it.
    assert result.retrieved_chunks
    assert result.citations

    retrieved_keys = {
        (c.document_id, c.chunk_id) for c in result.retrieved_chunks
    }
    citation_keys = {
        (c.document_id, c.chunk_id) for c in result.citations
    }
    # Citations never exceed the distinct retrieved set, and never invent keys.
    assert citation_keys.issubset(retrieved_keys)
    assert len(result.citations) == len(retrieved_keys)


def test_pipeline_emits_no_citations_when_no_evidence() -> None:
    from tests._retrieval_harness import DeterministicVectorStore

    empty_store = DeterministicVectorStore([])
    pipeline = QuestionAnsweringPipeline(
        conversation_context_builder=ConversationContextBuilder(),
        query_embedder=QueryEmbedder(LookupEmbeddings({})),
        hybrid_retriever=HybridRetriever(empty_store),
        metadata_filter=MetadataFilter(),
        reranker=Reranker(),
        context_builder=ContextBuilder(),
        prompt_builder=PromptBuilder(),
        response_generator=ResponseGenerator(_StubLlm()),
        citation_builder=CitationBuilder(),
        response_formatter=ResponseFormatter(),
        trace_observer=NoOpTraceObserver(),
    )
    result = pipeline.run(
        QuestionAnsweringPipelineRequest(
            application_id="app-1",
            knowledge_base_id="kb-1",
            query_text="What payment methods are accepted?",
            conversation_id="conversation-1",
            messages=[],
            top_k=5,
            request_id="request-no-evidence",
        )
    )

    assert result.retrieved_chunks == []
    assert result.citations == []
    assert result.answer_text  # safe fallback is still returned
