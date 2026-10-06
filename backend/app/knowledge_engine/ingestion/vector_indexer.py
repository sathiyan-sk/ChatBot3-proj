from __future__ import annotations

import logging
from dataclasses import dataclass

from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.shared.models import EmbeddedChunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class VectorIndexer:
    vector_store_contract: VectorStoreContract

    def index(self, embedded_chunks: list[EmbeddedChunk]) -> list[str]:
        indexed_chunk_ids: list[str] = []

        for index, chunk in enumerate(embedded_chunks, start=1):
            self.vector_store_contract.index_chunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata=chunk.metadata,
            )
            indexed_chunk_ids.append(chunk.chunk_id)
            if index % 10 == 0 or index == len(embedded_chunks):
                logger.info(
                    "Indexed document vectors",
                    extra={
                        "document_id": chunk.metadata.get("document_id"),
                        "completed_chunks": index,
                        "total_chunks": len(embedded_chunks),
                    },
                )

        if embedded_chunks:
            document_id = embedded_chunks[0].metadata.get("document_id")
            prune_stale = getattr(
                self.vector_store_contract,
                "delete_stale_document_chunks",
                None,
            )
            if document_id and callable(prune_stale):
                prune_stale(
                    document_id=document_id,
                    keep_chunk_ids=indexed_chunk_ids,
                )

        return indexed_chunk_ids