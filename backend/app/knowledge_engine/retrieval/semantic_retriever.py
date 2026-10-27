from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.shared.models import RetrievedChunk


@dataclass(slots=True)
class SemanticRetriever:
    """Responsible for vector (embedding) similarity search.

    Published-version filtering, knowledge-base isolation and application
    isolation are enforced inside the provider's SQL so every retrieval path
    is safe by construction.
    """

    vector_store_contract: VectorStoreContract

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if top_k <= 0 or not query_embedding:
            return []
        return self.vector_store_contract.similarity_search(
            knowledge_base_id=knowledge_base_id,
            query_embedding=query_embedding,
            top_k=top_k,
        )
