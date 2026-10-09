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
        indexed_chunk_ids = [chunk.chunk_id for chunk in embedded_chunks]
        batch_size = 100

        for offset in range(0, len(embedded_chunks), batch_size):
            batch = embedded_chunks[offset : offset + batch_size]
            self.vector_store_contract.index_chunks(batch)
            completed = offset + len(batch)
            if completed % 100 == 0 or completed == len(embedded_chunks):
                logger.info(
                    "Indexed document vectors",
                    extra={
                        "document_id": batch[-1].metadata.get("document_id"),
                        "completed_chunks": completed,
                        "total_chunks": len(embedded_chunks),
                    },
                )

        if embedded_chunks:
            document_id = embedded_chunks[0].metadata.get("document_id")
            ingestion_version = embedded_chunks[0].metadata.get(
                "ingestion_version"
            )
            prune_stale = getattr(
                self.vector_store_contract,
                "delete_stale_document_chunks",
                None,
            )
            if document_id and ingestion_version and callable(prune_stale):
                prune_stale(
                    document_id=document_id,
                    ingestion_version=int(ingestion_version),
                    keep_chunk_ids=indexed_chunk_ids,
                )

        return indexed_chunk_ids