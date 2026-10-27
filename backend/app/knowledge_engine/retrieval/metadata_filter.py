from __future__ import annotations

from app.knowledge_engine.shared.models import RetrievedChunk


class MetadataFilter:
    """Filters retrieved chunks for quality before reranking.

    Enforces a minimum relevance threshold (on the fused retrieval score) and
    removes redundant chunks: empty content, and near-duplicates produced by
    overlapping chunk windows (which would otherwise bloat the prompt with
    conflicting/duplicate passages).
    """

    def __init__(self, *, min_score: float = 0.0) -> None:
        self.min_score = min_score

    def apply(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        filtered: list[RetrievedChunk] = []
        seen: list[tuple[str, str]] = []  # (document_id, normalized content)

        for chunk in chunks:
            if not chunk.content or not chunk.content.strip():
                continue
            if chunk.score < self.min_score:
                continue

            normalized = self._normalize(chunk.content)
            overlap_index = self._find_overlap_index(
                seen, chunk.document_id, normalized
            )

            if overlap_index is not None:
                # Overlapping window within the SAME document: keep the more
                # complete (longer) chunk and drop the shorter, fully-contained
                # window it subsumes. Distinct sections that merely share a
                # leading sentence (or chunks from different documents) are
                # never collapsed, so no distinct evidence is discarded.
                if len(normalized) > len(seen[overlap_index][1]):
                    filtered[overlap_index] = chunk
                    seen[overlap_index] = (chunk.document_id, normalized)
                continue

            filtered.append(chunk)
            seen.append((chunk.document_id, normalized))

        return filtered

    @staticmethod
    def _normalize(content: str) -> str:
        """Whitespace-normalised, lower-cased content used for comparison."""
        return " ".join(content.lower().split())

    @staticmethod
    def _find_overlap_index(
        seen: list[tuple[str, str]], document_id: str, normalized: str
    ) -> int | None:
        """Index of a retained chunk whose leading text overlaps ``normalized``.

        Only chunks from the same ``document_id`` are compared: adjacent
        overlapping windows belong to a single document and share their leading
        text, so a chunk is treated as a duplicate (or a sub-window) of a
        retained chunk when one normalised content is a *full* prefix of the
        other. Two sections that merely begin with the same sentence keep
        diverging tails, so neither is a full prefix of the other and neither
        is dropped -- distinct evidence is always retained.
        """
        for index, (doc_id, retained) in enumerate(seen):
            if doc_id != document_id:
                continue
            if retained == normalized:
                return index
            if retained.startswith(normalized) or normalized.startswith(retained):
                return index
        return None
