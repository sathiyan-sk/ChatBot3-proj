from __future__ import annotations

import logging
from dataclasses import dataclass

from app.knowledge_engine.contracts.embeddings import EmbeddingsContract
from app.knowledge_engine.shared.models import DocumentChunk, EmbeddedChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class EmbeddingGenerator:
    embeddings_contract: EmbeddingsContract

    def generate(self, chunks: list[DocumentChunk]) -> list[EmbeddedChunk]:
        embedded_chunks: list[EmbeddedChunk] = []

        for index, chunk in enumerate(chunks, start=1):
            embedding = self.embeddings_contract.embed_query(chunk.content)
            embedded_chunks.append(
                EmbeddedChunk(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    embedding=embedding,
                    metadata=chunk.metadata,
                )
            )
            if index % 10 == 0 or index == len(chunks):
                logger.info(
                    "Generated document embeddings",
                    extra={
                        "document_id": chunk.metadata.get("document_id"),
                        "completed_chunks": index,
                        "total_chunks": len(chunks),
                    },
                )

        return embedded_chunks