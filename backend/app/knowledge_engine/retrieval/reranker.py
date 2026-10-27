from __future__ import annotations

import re
from dataclasses import replace

from app.knowledge_engine.shared.models import RetrievedChunk


class Reranker:
    """Relevance reranker for hybrid retrieval candidates.

    Fuses the (batch-relative) retrieval score with a lexical overlap signal so
    that passages directly answering the question outrank passages that are
    merely topically close. Multi-part / comparative queries benefit because a
    chunk must cover several query terms to score well.

    Diversity (cross-document coverage) and token budgeting are intentionally
    left to :class:`~app.knowledge_engine.retrieval.context_builder.ContextBuilder`
    so ranking and context construction remain separable concerns.
    """

    def __init__(self, *, lexical_weight: float = 0.4) -> None:
        if not 0.0 <= lexical_weight <= 1.0:
            raise ValueError("lexical_weight must be between 0.0 and 1.0.")
        self.lexical_weight = lexical_weight

    def rerank(
        self,
        *,
        query_text: str,
        chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if not chunks or top_k <= 0:
            return []

        query_tokens = set(self._tokenize(query_text))

        retrieval_scores = [chunk.score for chunk in chunks]
        max_score = max(retrieval_scores) if retrieval_scores else 0.0
        min_score = min(retrieval_scores) if retrieval_scores else 0.0
        score_range = (max_score - min_score) or 1.0

        scored_chunks: list[tuple[RetrievedChunk, float]] = []
        for chunk in chunks:
            normalized_retrieval = (chunk.score - min_score) / score_range

            chunk_tokens = set(self._tokenize(chunk.content))
            overlap = len(query_tokens & chunk_tokens)
            overlap_ratio = overlap / max(len(query_tokens), 1)

            relevance = (
                (1.0 - self.lexical_weight) * normalized_retrieval
                + self.lexical_weight * overlap_ratio
            )
            scored_chunks.append((chunk, relevance))

        scored_chunks.sort(key=lambda item: item[1], reverse=True)

        return [
            replace(chunk, score=score)
            for chunk, score in scored_chunks[:top_k]
        ]

    def _tokenize(self, text: str) -> list[str]:
        # Simple tokenization: lowercase, remove punctuation, split
        text = text.lower()
        tokens = re.findall(r"\b[a-z0-9]+\b", text)
        # Remove common stopwords
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can", "need",
            "it", "its", "this", "that", "these", "those", "i", "you", "he",
            "she", "we", "they", "what", "which", "who", "whom", "whose",
        }
        return [t for t in tokens if t not in stopwords]
