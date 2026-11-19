from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.exceptions import ApplicationError


def validate_embedding_dimension(
    embedding: list[float],
    *,
    expected_dimension: int | None,
) -> list[float]:
    if expected_dimension is None:
        return embedding
    if len(embedding) != expected_dimension:
        raise ApplicationError(
            message=(
                f"Embedding dimension mismatch: expected {expected_dimension}, "
                f"received {len(embedding)}."
            ),
            code="embedding_dimension_mismatch",
            status_code=502,
        )
    return embedding


class EmbeddingsContract(ABC):
    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        raise NotImplementedError