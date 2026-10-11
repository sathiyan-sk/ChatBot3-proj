from __future__ import annotations

from abc import ABC, abstractmethod

from app.knowledge_engine.shared.models import EmbeddedChunk, RetrievedChunk


class VectorStoreContract(ABC):
    @abstractmethod
    def index_chunk(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        raise NotImplementedError

    def index_chunks(self, chunks: list[EmbeddedChunk]) -> None:
        for chunk in chunks:
            self.index_chunk(
                chunk_id=chunk.chunk_id,
                content=chunk.content,
                embedding=chunk.embedding,
                metadata=chunk.metadata,
            )

    def delete_obsolete_document_versions(
        self,
        *,
        document_id: str,
        keep_version: int,
    ) -> int:
        raise NotImplementedError

    def verify_document_version(
        self,
        *,
        document_id: str,
        ingestion_version: int,
        expected_chunk_ids: list[str],
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    def similarity_search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError

    @abstractmethod
    def keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        raise NotImplementedError