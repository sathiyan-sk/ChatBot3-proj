"""Reliability: tenant isolation, document replacement/versioning, and the
DB-layer guarantees (version scoping, partial-index verification).

Tenant isolation and document-replacement are asserted with an in-memory store
that models the same ``knowledge_base_id`` partitioning the provider enforces in
SQL, so they run without Postgres. The Postgres/SQLAlchemy-level guarantees are
asserted with ``importorskip`` guards so they are collected in CI against the
real ``PgVectorProvider`` but skip cleanly here.
"""

from __future__ import annotations

import pytest

from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from tests._retrieval_harness import (
    E_REFUND,
    EvalChunk,
    KB_1,
    KB_2,
    DeterministicVectorStore,
)


def _tenant_corpus() -> list[EvalChunk]:
    return [
        EvalChunk(
            chunk_id="c_refund",
            document_id="doc_billing",
            knowledge_base_id=KB_1,
            document_title="Billing policy",
            content="Refunds are accepted within 30 days of purchase.",
            embedding=E_REFUND,
        ),
        EvalChunk(
            chunk_id="other_refund",
            document_id="doc_other",
            knowledge_base_id=KB_2,
            document_title="Other tenant policy",
            content="Refunds only via carrier pigeon within 7 days.",
            embedding=E_REFUND,
        ),
    ]


def test_retrieval_contract_scopes_by_knowledge_base_id() -> None:
    """A query to tenant KB_2 must never surface KB_1 chunks (and vice-versa).

    The retrieval contract threads ``knowledge_base_id`` through every search; the
    ``DeterministicVectorStore`` partitions by it exactly as ``PgVectorProvider``
    SQL does, so cross-tenant leakage is impossible at the call site.
    """
    store = DeterministicVectorStore(_tenant_corpus())
    retriever = HybridRetriever(store)

    tenant_two = retriever.retrieve(
        knowledge_base_id=KB_2,
        query_text="Refunds accepted within 30 days?",
        query_embedding=E_REFUND,
        top_k=10,
    )
    tenant_two_ids = {c.chunk_id for c in tenant_two}
    assert tenant_two_ids == {"other_refund"}

    tenant_one = retriever.retrieve(
        knowledge_base_id=KB_1,
        query_text="Refunds accepted within 30 days?",
        query_embedding=E_REFUND,
        top_k=10,
    )
    tenant_one_ids = {c.chunk_id for c in tenant_one}
    assert "other_refund" not in tenant_one_ids
    # KB_1's distinctive content never bleeds into KB_2 results.
    kb_two_text = " ".join(c.content for c in tenant_two)
    assert "accepted within 30 days" not in kb_two_text


def test_document_replacement_drops_obsolete_version() -> None:
    """Replacing a document makes its previous-version chunks unretrievable.

    Models the index-v3 -> index-v4 -> delete_obsolete(keep=v4) flow at the
    contract level: once replaced, obsolete chunk ids no longer reach retrieval.
    """
    store = DeterministicVectorStore(
        [
            EvalChunk(
                chunk_id="c_refund_v1",
                document_id="doc_billing",
                knowledge_base_id=KB_1,
                document_title="Billing policy",
                content="The old refund policy is 7 days.",
                embedding=E_REFUND,
            )
        ]
    )
    store.replace_document(
        KB_1,
        "doc_billing",
        [
            EvalChunk(
                chunk_id="c_refund_v2",
                document_id="doc_billing",
                knowledge_base_id=KB_1,
                document_title="Billing policy",
                content="Refunds are accepted within 30 days of purchase.",
                embedding=E_REFUND,
            )
        ],
    )

    retriever = HybridRetriever(store)
    results = retriever.retrieve(
        knowledge_base_id=KB_1,
        query_text="How long do I have to request a refund?",
        query_embedding=E_REFUND,
        top_k=10,
    )
    ids = {c.chunk_id for c in results}
    assert "c_refund_v2" in ids
    assert "c_refund_v1" not in ids


def test_pgvector_replace_flow_excludes_obsolete_version() -> None:
    """DB-layer: re-indexing v4 then deleting obsolete v3 excludes old chunks.

    Runs against the real ``PgVectorProvider`` SQL using an in-memory session
    fake; skipped where SQLAlchemy/PgVector are unavailable.
    """
    pytest.importorskip("sqlalchemy")
    pytest.importorskip("pgvector")
    from types import SimpleNamespace
    from typing import cast

    from sqlalchemy.orm import Session

    from app.config.settings import Settings
    from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
    from app.knowledge_engine.shared.models import EmbeddedChunk

    class _ExecutionResult:
        def __init__(self, rows=None):
            self.rows = rows or []

        def mappings(self):
            return self

        def all(self):
            return self.rows

    class _Session:
        def __init__(self):
            self.executions = []
            self.result = _ExecutionResult()

        def execute(self, statement, parameters):
            self.executions.append((str(statement), parameters))
            return self.result

    def _chunk(chunk_id, version):
        return EmbeddedChunk(
            chunk_id=chunk_id,
            content="content",
            embedding=[0.1, 0.2],
            metadata={
                "document_id": "doc-1",
                "knowledge_base_id": "kb-1",
                "document_title": "Guide",
                "source_identifier": "guide.pdf",
                "ingestion_version": str(version),
            },
        )

    session = _Session()
    provider = PgVectorProvider(
        settings=cast(
            Settings,
            SimpleNamespace(vector_store_table_name="document_chunks"),
        ),
        session=cast(Session, session),
    )
    provider.index_chunks([_chunk(f"doc-1-chunk-{i}-v3", 3) for i in range(3)])
    provider.index_chunks([_chunk(f"doc-1-chunk-{i}-v4", 4) for i in range(3)])

    provider.delete_obsolete_document_versions(document_id="doc-1", keep_version=4)
    statement, parameters = session.executions[-1]
    assert "ingestion_version <> :keep_version" in statement.lower()
    assert "document_id = cast(:document_id as text)" in statement.lower()
    assert parameters == {"document_id": "doc-1", "keep_version": 4}

    v4_ids = [f"doc-1-chunk-{i}-v4" for i in range(3)]
    session.result = _ExecutionResult(rows=[(rid,) for rid in v4_ids])
    assert provider.verify_document_version(
        document_id="doc-1", ingestion_version=4, expected_chunk_ids=v4_ids
    )
    # Obsolete v3 ids are not part of the verified v4 set.
    assert not provider.verify_document_version(
        document_id="doc-1",
        ingestion_version=4,
        expected_chunk_ids=v4_ids + ["doc-1-chunk-0-v3"],
    )
