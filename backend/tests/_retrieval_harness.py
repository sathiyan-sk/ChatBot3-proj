"""Shared in-memory fixtures and helpers for the retrieval QA suites.

These harnesses model the *contracts* (not a real vector DB) so the retrieval,
context and citation logic can be validated deterministically without Postgres or
an embedding model. The real tenant-isolation / version-scoping guarantees live
in ``PgVectorProvider`` SQL and are asserted separately in
``test_vector_batch_indexing.py``.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from app.knowledge_engine.contracts.embeddings import EmbeddingsContract
from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.retrieval.context_builder import ContextBuilder
from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.reranker import Reranker
from app.knowledge_engine.shared.models import RetrievedChunk

# Orthogonal 4-dim topic vectors so cosine similarity is deterministic and
# unambiguous: a query aligned with a topic scores ~1.0 against that topic's
# chunk and ~0.0 against every other topic.
E_REFUND = [1.0, 0.0, 0.0, 0.0]
E_BILLING = [0.0, 1.0, 0.0, 0.0]
E_PAYMENT = [0.0, 0.0, 1.0, 0.0]
E_RECEIPT = [0.0, 0.0, 0.0, 1.0]
E_NONE = [0.0, 0.0, 0.0, 0.0]

KB_1 = "kb-1"
KB_2 = "kb-2"


@dataclass(slots=True)
class EvalChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    document_title: str
    content: str
    embedding: list[float]


@dataclass(slots=True)
class EvalCase:
    name: str
    query: str
    query_embedding: list[float]
    knowledge_base_id: str
    gold: list[str]  # ordered, expected chunk_ids


# A small, coherent two-document corpus. doc_billing holds refund + billing-cycle
# evidence; doc_payments holds payment-method + receipt evidence.
CORPUS: list[EvalChunk] = [
    EvalChunk(
        chunk_id="c_refund",
        document_id="doc_billing",
        knowledge_base_id=KB_1,
        document_title="Billing policy",
        content="Refunds are accepted within 30 days of purchase.",
        embedding=E_REFUND,
    ),
    EvalChunk(
        chunk_id="c_cycle",
        document_id="doc_billing",
        knowledge_base_id=KB_1,
        document_title="Billing policy",
        content="The billing cycle closes at midnight on the last day of each month.",
        embedding=E_BILLING,
    ),
    EvalChunk(
        chunk_id="c_payment",
        document_id="doc_payments",
        knowledge_base_id=KB_1,
        document_title="Payments",
        content="Accepted payment methods include credit card, debit card, or bank transfer.",
        embedding=E_PAYMENT,
    ),
    EvalChunk(
        chunk_id="c_receipt",
        document_id="doc_payments",
        knowledge_base_id=KB_1,
        document_title="Payments",
        content="A receipt is emailed automatically after a successful payment.",
        embedding=E_RECEIPT,
    ),
    # A second tenant's copy so cross-tenant leakage can be asserted.
    EvalChunk(
        chunk_id="other_refund",
        document_id="doc_other",
        knowledge_base_id=KB_2,
        document_title="Other tenant policy",
        content="Refunds only via carrier pigeon within 7 days.",
        embedding=E_REFUND,
    ),
]


# Repeatable evaluation set: each query is anchored to a topic embedding and
# declares which chunk_ids constitute correct evidence (ordered by expected rank).
EVAL_CASES: list[EvalCase] = [
    EvalCase(
        name="refund_window",
        query="How long do I have to request a refund?",
        query_embedding=E_REFUND,
        knowledge_base_id=KB_1,
        gold=["c_refund"],
    ),
    EvalCase(
        name="billing_close",
        query="When does the billing cycle end?",
        query_embedding=E_BILLING,
        knowledge_base_id=KB_1,
        gold=["c_cycle"],
    ),
    EvalCase(
        name="payment_methods",
        query="What payment methods are accepted?",
        query_embedding=E_PAYMENT,
        knowledge_base_id=KB_1,
        gold=["c_payment"],
    ),
    EvalCase(
        name="multi_part_refund_and_payment",
        query="How long for a refund and what payment methods exist?",
        query_embedding=[0.7, 0.0, 0.3, 0.0],
        knowledge_base_id=KB_1,
        gold=["c_refund", "c_payment"],
    ),
]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


class DeterministicVectorStore(VectorStoreContract):
    """In-memory store partitioning chunks by ``knowledge_base_id``.

    Mirrors the contract enforced by ``PgVectorProvider`` SQL: every search is
    scoped to a single tenant's chunks, so cross-tenant leakage cannot occur.
    """

    def __init__(self, chunks: list[EvalChunk] | None = None) -> None:
        self._chunks = list(chunks or [])
        self.index_calls = 0
        self.similarity_search_calls = 0
        self.keyword_search_calls = 0

    def _for_kb(self, knowledge_base_id: str) -> list[EvalChunk]:
        return [c for c in self._chunks if c.knowledge_base_id == knowledge_base_id]

    def replace_document(
        self,
        knowledge_base_id: str,
        document_id: str,
        new_chunks: list[EvalChunk],
    ) -> None:
        """Atomically swap all chunks for one document (models re-index + cleanup)."""
        self._chunks = [
            c
            for c in self._chunks
            if not (
                c.knowledge_base_id == knowledge_base_id
                and c.document_id == document_id
            )
        ] + list(new_chunks)

    def index_chunk(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        self.index_calls += 1

    @staticmethod
    def _to_retrieved(chunk: EvalChunk, score: float) -> RetrievedChunk:
        return RetrievedChunk(
            chunk_id=chunk.chunk_id,
            document_id=chunk.document_id,
            document_title=chunk.document_title,
            content=chunk.content,
            score=score,
            source_uri=None,
            metadata={},
        )

    def similarity_search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        self.similarity_search_calls += 1
        if top_k <= 0 or not query_embedding:
            return []
        cands = self._for_kb(knowledge_base_id)
        scored = [(c, cosine(c.embedding, query_embedding)) for c in cands]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [self._to_retrieved(c, sim) for c, sim in scored[:top_k]]

    def keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        self.keyword_search_calls += 1
        if top_k <= 0 or not query_text or not query_text.strip():
            return []
        terms = [t for t in re.findall(r"\w+", query_text.lower()) if t]
        cands = self._for_kb(knowledge_base_id)
        scored = [
            (c, sum(c.content.lower().count(t) for t in terms)) for c in cands
        ]
        scored = [(c, s) for c, s in scored if s > 0]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [self._to_retrieved(c, float(s)) for c, s in scored[:top_k]]


class LookupEmbeddings(EmbeddingsContract):
    """Returns the precomputed embedding for a given query string."""

    def __init__(self, mapping: dict[str, list[float]]) -> None:
        self._mapping = mapping

    def embed_query(self, text: str) -> list[float]:
        return self._mapping.get(text, E_NONE)


@dataclass(slots=True)
class Measure:
    fused_ids: list[str]
    context_ids: list[str]
    gold: list[str]

    def recall_at(self, k: int) -> float:
        if not self.gold:
            return 1.0
        hits = len(set(self.gold) & set(self.fused_ids[:k]))
        return hits / len(self.gold)

    def mrr(self) -> float:
        if not self.gold:
            return 0.0
        for rank, chunk_id in enumerate(self.fused_ids, start=1):
            if chunk_id == self.gold[0]:
                return 1.0 / rank
        return 0.0

    def context_recall(self) -> float:
        if not self.gold:
            return 1.0
        hits = len(set(self.gold) & set(self.context_ids))
        return hits / len(self.gold)


def retrieve_and_measure(
    case: EvalCase,
    *,
    initial_top_k: int = 10,
    context_max_chunks: int = 5,
    corpus: list[EvalChunk] | None = None,
) -> Measure:
    """Run retrieve -> filter -> rerank -> context and capture evidence flow."""
    store = DeterministicVectorStore(corpus or CORPUS)
    retriever = HybridRetriever(vector_store_contract=store)
    fused = retriever.retrieve(
        knowledge_base_id=case.knowledge_base_id,
        query_text=case.query,
        query_embedding=case.query_embedding,
        top_k=initial_top_k,
    )
    filtered = MetadataFilter().apply(fused)
    reranked = Reranker().rerank(
        query_text=case.query, chunks=filtered, top_k=initial_top_k
    )
    context = ContextBuilder().build(
        chunks=reranked, max_chunks=context_max_chunks, max_tokens=None
    )
    return Measure(
        fused_ids=[c.chunk_id for c in fused],
        context_ids=[c.chunk_id for c in context],
        gold=case.gold,
    )
