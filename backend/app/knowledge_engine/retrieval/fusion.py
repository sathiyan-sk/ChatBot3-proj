from __future__ import annotations

from dataclasses import dataclass, replace

from app.knowledge_engine.shared.models import RetrievedChunk


@dataclass(slots=True)
class ReciprocalRankFusion:
    """Combine candidate lists using Reciprocal Rank Fusion (RRF).

    RRF is score-scale agnostic: it only depends on the *rank* at which a
    chunk appears in each list, so the disparate scales of cosine similarity
    (0–1) and ``ts_rank_cd`` (>1 possible) no longer distort the blend. A
    chunk that appears in both candidate lists receives a higher fused score,
    which is exactly the behaviour we want for confident matches.
    """

    rrf_k: int = 60

    @staticmethod
    def _key(chunk: RetrievedChunk) -> str:
        return f"{chunk.document_id}:{chunk.chunk_id}"

    def fuse(
        self,
        *,
        semantic_chunks: list[RetrievedChunk],
        keyword_chunks: list[RetrievedChunk],
        top_k: int,
    ) -> list[RetrievedChunk]:
        if top_k <= 0:
            return []

        scores: dict[str, float] = {}
        rank_map: dict[str, RetrievedChunk] = {}

        for rank, chunk in enumerate(semantic_chunks, start=1):
            key = self._key(chunk)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            if key not in rank_map:
                rank_map[key] = chunk

        for rank, chunk in enumerate(keyword_chunks, start=1):
            key = self._key(chunk)
            scores[key] = scores.get(key, 0.0) + 1.0 / (self.rrf_k + rank)
            if key not in rank_map:
                rank_map[key] = chunk

        ordered_keys = sorted(scores, key=lambda key: scores[key], reverse=True)
        return [
            replace(rank_map[key], score=scores[key])
            for key in ordered_keys[:top_k]
        ]
