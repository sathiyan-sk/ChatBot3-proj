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
        embed_documents = getattr(
            self.embeddings_contract,
            "embed_documents",
            None,
        )
        if callable(embed_documents):
            embeddings = embed_documents([chunk.content for chunk in chunks])
            if len(embeddings) != len(chunks):
                raise ValueError(
                    "Embedding provider returned a different number of vectors than chunks."
                )
        else:
            embeddings = [
                self.embeddings_contract.embed_query(chunk.content)
                for chunk in chunks
            ]

        for index, (chunk, embedding) in enumerate(
            zip(chunks, embeddings),
            start=1,
        ):
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