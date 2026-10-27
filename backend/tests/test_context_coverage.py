"""Context coverage: the final evidence context retains the right chunks.

Validates that the retrieved -> rerank -> context-build stage (MMR diversity +
token budgeting) keeps (a) every piece of evidence needed for multi-part
queries, (b) evidence spanning multiple documents, and (c) respect for the
``max_chunks`` / ``max_tokens`` bounds.
"""

from __future__ import annotations

from app.knowledge_engine.retrieval.context_builder import ContextBuilder
from app.knowledge_engine.shared.models import RetrievedChunk
from tests._retrieval_harness import (
    CORPUS,
    EVAL_CASES,
    EvalCase,
    E_PAYMENT,
    retrieve_and_measure,
)


def _case(name: str) -> EvalCase:
    for case in EVAL_CASES:
        if case.name == name:
            return case
    raise AssertionError(f"missing eval case: {name}")


def test_multi_part_query_keeps_all_evidence_chunks() -> None:
    case = _case("multi_part_refund_and_payment")
    measure = retrieve_and_measure(case, context_max_chunks=5)
    assert set(measure.context_ids) >= {"c_refund", "c_payment"}
    assert measure.context_recall() == 1.0
    assert measure.recall_at(10) == 1.0


def test_context_spans_multiple_documents() -> None:
    # The two gold chunks live in two distinct documents; MMR must not let one
    # document monopolise the context window.
    case = _case("multi_part_refund_and_payment")
    measure = retrieve_and_measure(case, context_max_chunks=5)
    context_docs = {
        chunk.document_id
        for chunk in CORPUS
        if chunk.chunk_id in measure.context_ids
    }
    assert context_docs == {"doc_billing", "doc_payments"}


def test_context_respects_max_chunks_cap() -> None:
    chunks = [
        RetrievedChunk(
            chunk_id=f"c{i}",
            document_id=f"doc{i}",
            document_title="t",
            content=f"evidence chunk number {i} with enough text",
            score=1.0 - i * 0.1,
            source_uri=None,
            metadata={},
        )
        for i in range(6)
    ]
    selected = ContextBuilder().build(chunks=chunks, max_chunks=2, max_tokens=None)
    assert len(selected) == 2
    assert selected[0].score >= selected[1].score


def test_context_respects_token_budget_and_trims_to_boundary() -> None:
    # Three distinct documents, each content just over the 12-char budget
    # (max_tokens=3, chars_per_token=4 => 12 chars). Only the top-ranked chunk
    # can fully fit; the context must never exceed the budget.
    chunks = [
        RetrievedChunk(
            chunk_id="c0",
            document_id="doc_a",
            document_title="t",
            content="a" * 30,
            score=0.9,
            source_uri=None,
            metadata={},
        ),
        RetrievedChunk(
            chunk_id="c1",
            document_id="doc_b",
            document_title="t",
            content="b" * 30,
            score=0.8,
            source_uri=None,
            metadata={},
        ),
        RetrievedChunk(
            chunk_id="c2",
            document_id="doc_c",
            document_title="t",
            content="c" * 30,
            score=0.7,
            source_uri=None,
            metadata={},
        ),
    ]
    builder = ContextBuilder(chars_per_token=4)
    selected = builder.build(chunks=chunks, max_chunks=10, max_tokens=3)

    total_chars = sum(len(c.content) for c in selected)
    assert total_chars <= 12  # budget_chars = 3 * 4
    assert selected  # best evidence is retained, not dropped entirely
    assert all(len(c.content) <= 12 for c in selected)
    assert selected[0].content == "a" * 12  # trimmed on a clean boundary


def test_retrieval_reaches_context_with_realistic_query() -> None:
    # End-to-end: a single-evidence query's gold chunk must be present in the
    # final context built by the real pipeline stages.
    case = EvalCase(
        name="payment_methods",
        query="What payment methods are accepted?",
        query_embedding=E_PAYMENT,
        knowledge_base_id="kb-1",
        gold=["c_payment"],
    )
    measure = retrieve_and_measure(case, context_max_chunks=5)
    assert "c_payment" in measure.context_ids


def test_context_never_exceeds_max_chunks_under_token_budget() -> None:
    # Even when a token budget would otherwise permit more, ``max_chunks`` is the
    # hard cap on the number of context passages.
    chunks = [
        RetrievedChunk(
            chunk_id=f"c{i}",
            document_id=f"doc{i}",
            document_title="t",
            content="evidence " + ("x" * (i + 1)),
            score=1.0 - i * 0.1,
            source_uri=None,
            metadata={},
        )
        for i in range(5)
    ]
    selected = ContextBuilder().build(
        chunks=chunks, max_chunks=2, max_tokens=50
    )
    assert len(selected) <= 2
    assert selected[0].score >= selected[1].score
