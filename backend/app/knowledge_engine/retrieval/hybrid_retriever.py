from __future__ import annotations

import logging

from dataclasses import dataclass, field

from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.retrieval.fusion import ReciprocalRankFusion
from app.knowledge_engine.retrieval.keyword_retriever import KeywordRetriever
from app.knowledge_engine.retrieval.semantic_retriever import SemanticRetriever
from app.knowledge_engine.shared.models import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HybridRetriever:
    """Orchestrates hybrid (semantic + keyword) retrieval and rank fusion.

    The two candidate lists are fused with Reciprocal Rank Fusion, which is
    insensitive to the different score scales returned by the vector index
    (cosine similarity) and the full-text index (ts_rank_cd). A chunk present
    in both lists naturally scores higher, surfacing the most confident
    matches.

    Concurrency note: the two searches target the same SQLAlchemy ``Session``
    / DB connection owned by the provider. SQLAlchemy sync sessions are not
    safe for concurrent ``execute`` on a shared connection, so the searches run
    sequentially to preserve reliability. The codebase already establishes the
    safe parallel pattern (``session_factory()`` checked out per thread) in the
    ingestion worker; switching to parallel retrieval later only requires giving
    each retriever its own session rather than changing this orchestration.
    """

    vector_store_contract: VectorStoreContract
    rrf_k: int = 60
    semantic_retriever: SemanticRetriever = field(init=False)
    keyword_retriever: KeywordRetriever = field(init=False)
    fusion: ReciprocalRankFusion = field(init=False)

    def __post_init__(self) -> None:
        self.semantic_retriever = SemanticRetriever(
            vector_store_contract=self.vector_store_contract,
        )
        self.keyword_retriever = KeywordRetriever(
            vector_store_contract=self.vector_store_contract,
        )
        self.fusion = ReciprocalRankFusion(rrf_k=self.rrf_k)

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        semantic_chunks = self.semantic_retriever.retrieve(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )
        keyword_chunks = self.keyword_retriever.retrieve(
            knowledge_base_id=knowledge_base_id,
            query_text=query_text,
            top_k=top_k,
        )

        logger.debug(
            "Hybrid retrieval produced %d semantic and %d keyword candidates.",
            len(semantic_chunks),
            len(keyword_chunks),
        )

        return self.fusion.fuse(
            semantic_chunks=semantic_chunks,
            keyword_chunks=keyword_chunks,
            top_k=top_k,
        )
