from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.shared.models import RetrievedChunk


@dataclass(slots=True)
class KeywordRetriever:
    """Responsible for exact-term / full-text keyword search.

    The provider applies the same application, knowledge-base and
    published-version filters as the semantic path.
    """

    vector_store_contract: VectorStoreContract

    def retrieve(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        if top_k <= 0 or not query_text or not query_text.strip():
            return []
        return self.vector_store_contract.keyword_search(
            knowledge_base_id=knowledge_base_id,
            query_text=query_text,
            top_k=top_k,
        )
