from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_engine.contracts.embeddings import (
    EmbeddingsContract,
    validate_embedding_dimension,
)


@dataclass(slots=True)
class QueryEmbedder:
    embeddings_contract: EmbeddingsContract
    expected_dimension: int | None = None

    def embed(self, query_text: str) -> list[float]:
        return validate_embedding_dimension(
            self.embeddings_contract.embed_query(query_text),
            expected_dimension=self.expected_dimension,
        )