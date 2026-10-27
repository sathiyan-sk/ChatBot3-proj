from __future__ import annotations

import math
from dataclasses import replace

from app.knowledge_engine.shared.models import RetrievedChunk


class ContextBuilder:
    """Select and trim the final evidence context for generation.

    Responsibilities:
      * Balance evidence across multiple documents so a single dominant
        document cannot exhaust the context budget (cross-document reasoning).
      * Enforce a token budget so prompts stay bounded (latency / cost).
      * Preserve chunk content readability (trim on whitespace boundaries).
    """

    def __init__(
        self,
        *,
        diversity_lambda: float = 0.7,
        chars_per_token: int = 4,
        max_chunk_chars: int = 600,
    ) -> None:
        self.diversity_lambda = diversity_lambda
        self.chars_per_token = max(1, chars_per_token)
        self.max_chunk_chars = max(1, max_chunk_chars)

    def build(
        self,
        *,
        chunks: list[RetrievedChunk],
        max_chunks: int,
        max_tokens: int | None = None,
    ) -> list[RetrievedChunk]:
        if not chunks or max_chunks <= 0:
            return []

        # Chunks arrive relevance-sorted (reranker output). Greedily pick the
        # next chunk maximising: lambda * relevance - (1 - lambda) * sim(doc).
        # Document-level similarity (1.0 when the document is already
        # represented) yields multi-document coverage without starving the
        # highest-relevance chunks.
        remaining = list(chunks)
        selected: list[RetrievedChunk] = []
        represented_documents: set[str] = set()

        while remaining and len(selected) < max_chunks:
            best_index = 0
            best_score = -math.inf
            for index, chunk in enumerate(remaining):
                same_document = (
                    1.0 if chunk.document_id in represented_documents else 0.0
                )
                mmr_score = (
                    self.diversity_lambda * chunk.score
                    - (1.0 - self.diversity_lambda) * same_document
                )
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_index = index

            chosen = remaining.pop(best_index)
            selected.append(chosen)
            represented_documents.add(chosen.document_id)

        if max_tokens:
            return self._enforce_token_budget(selected, max_tokens)

        return [self._trim_chunk(chunk) for chunk in selected if chunk.content.strip()]

    def _enforce_token_budget(
        self,
        chunks: list[RetrievedChunk],
        max_tokens: int,
    ) -> list[RetrievedChunk]:
        budget_chars = max_tokens * self.chars_per_token
        result: list[RetrievedChunk] = []
        used = 0
        for chunk in chunks:
            if used >= budget_chars:
                break
            content = chunk.content.strip()
            if len(content) > self.max_chunk_chars:
                content = content[: self.max_chunk_chars]
            budget_left = budget_chars - used
            if len(content) > budget_left:
                content = content[:budget_left].rstrip()
            if not content:
                continue
            used += len(content)
            result.append(replace(chunk, content=content))
        return result

    def _trim_chunk(self, chunk: RetrievedChunk) -> RetrievedChunk:
        if len(chunk.content) <= self.max_chunk_chars:
            return chunk
        return replace(chunk, content=chunk.content[: self.max_chunk_chars])
