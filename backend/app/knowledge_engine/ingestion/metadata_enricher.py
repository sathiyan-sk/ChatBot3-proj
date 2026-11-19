from __future__ import annotations

from dataclasses import dataclass

from app.knowledge_engine.shared.helpers import coalesce_metadata
from app.knowledge_engine.shared.models import DocumentChunk


@dataclass(slots=True)
class MetadataEnricher:
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimensions: int | None = None

    def enrich(
        self,
        *,
        chunks: list[DocumentChunk],
        document_id: str,
        knowledge_base_id: str,
        source_type: str,
        source_identifier: str,
        document_title: str,
        document_metadata: dict[str, str],
        ingestion_version: int,
    ) -> list[DocumentChunk]:
        enriched_chunks: list[DocumentChunk] = []

        for chunk in chunks:
            enriched_chunks.append(
                DocumentChunk(
                    chunk_id=chunk.chunk_id,
                    content=chunk.content,
                    metadata=coalesce_metadata(
                        chunk.metadata,
                        document_metadata,
                        {
                            "document_id": document_id,
                            "knowledge_base_id": knowledge_base_id,
                            "source_type": source_type,
                            "source_identifier": source_identifier,
                            "document_title": document_title,
                            "ingestion_version": str(ingestion_version),
                            **(
                                {
                                    "embedding_provider": self.embedding_provider,
                                    "embedding_model": self.embedding_model,
                                    "embedding_dimensions": str(
                                        self.embedding_dimensions
                                    ),
                                }
                                if self.embedding_provider
                                and self.embedding_model
                                and self.embedding_dimensions is not None
                                else {}
                            ),
                        },
                    ),
                )
            )

        return enriched_chunks