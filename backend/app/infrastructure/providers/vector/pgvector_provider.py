from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.shared.models import RetrievedChunk


@dataclass(slots=True)
class PgVectorProvider(VectorStoreContract):
    settings: Settings
    session: Session

    def index_chunk(
        self,
        *,
        chunk_id: str,
        content: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        knowledge_base_id = metadata.get("knowledge_base_id")
        document_id = metadata.get("document_id")
        document_title = metadata.get("document_title")

        if not knowledge_base_id or not document_id or not document_title:
            raise ApplicationError(
                message="Indexed chunk metadata is incomplete.",
                code="vector_index_metadata_invalid",
                status_code=422,
            )

        source_uri = metadata.get("source_identifier")
        embedding_literal = self._to_pgvector_literal(embedding)
        table_name = self.settings.vector_store_table_name

        statement = text(
            f"""
            insert into {table_name} (
                chunk_id,
                knowledge_base_id,
                document_id,
                document_title,
                content,
                source_uri,
                metadata_json,
                embedding
            )
            values (
                :chunk_id,
                cast(:knowledge_base_id as text),
                cast(:document_id as text),
                :document_title,
                :content,
                :source_uri,
                cast(:metadata_json as jsonb),
                cast(:embedding as vector)
            )
            on conflict (chunk_id)
            do update set
                knowledge_base_id = excluded.knowledge_base_id,
                document_id = excluded.document_id,
                document_title = excluded.document_title,
                content = excluded.content,
                source_uri = excluded.source_uri,
                metadata_json = excluded.metadata_json,
                embedding = excluded.embedding
            """
        )

        self.session.execute(
            statement,
            {
                "chunk_id": chunk_id,
                "knowledge_base_id": str(knowledge_base_id) if not isinstance(knowledge_base_id, str) else knowledge_base_id,
                "document_id": str(document_id) if not isinstance(document_id, str) else document_id,
                "document_title": document_title,
                "content": content,
                "source_uri": source_uri,
                "metadata_json": self._to_json(metadata),
                "embedding": embedding_literal,
            },
        )

    def similarity_search(
        self,
        *,
        knowledge_base_id: str,
        query_embedding: list[float],
        top_k: int,
    ) -> list[RetrievedChunk]:
        table_name = self.settings.vector_store_table_name

        statement = text(
            f"""
            select
                chunk_id,
                document_id,
                document_title,
                content,
                source_uri,
                metadata_json,
                1 - (embedding <=> cast(:query_embedding as vector)) as score
            from {table_name}
            where knowledge_base_id = cast(:knowledge_base_id as text)
            order by embedding <=> cast(:query_embedding as vector)
            limit :top_k
            """
        )

        result = self.session.execute(
            statement,
            {
                "knowledge_base_id": str(knowledge_base_id) if not isinstance(knowledge_base_id, str) else knowledge_base_id,
                "query_embedding": self._to_pgvector_literal(query_embedding),
                "top_k": top_k,
            },
        )
        return [
            self._map_row_to_retrieved_chunk(dict(row))
            for row in result.mappings().all()
        ]

    def keyword_search(
        self,
        *,
        knowledge_base_id: str,
        query_text: str,
        top_k: int,
    ) -> list[RetrievedChunk]:
        table_name = self.settings.vector_store_table_name

        statement = text(
            f"""
            select
                chunk_id,
                document_id,
                document_title,
                content,
                source_uri,
                metadata_json,
                ts_rank_cd(
                to_tsvector('english', content),
                plainto_tsquery('english', :query_text)
                ) as score
            from {table_name}
            where knowledge_base_id = cast(:knowledge_base_id as text)
              and to_tsvector('english', content) @@ plainto_tsquery('english', :query_text)
            order by score desc
            limit :top_k
            """
        )

        result = self.session.execute(
            statement,
            {
                "knowledge_base_id": str(knowledge_base_id) if not isinstance(knowledge_base_id, str) else knowledge_base_id,
                "query_text": query_text,
                "top_k": top_k,
            },
        )
        return [
            self._map_row_to_retrieved_chunk(dict(row))
            for row in result.mappings().all()
        ]

    def delete_document_chunks(self, *, document_id: str) -> int:
        """Remove all indexed chunks belonging to a document.

        Returns the number of deleted rows so callers can log/verify.
        """
        table_name = self.settings.vector_store_table_name

        statement = text(
            f"""
            delete from {table_name}
            where document_id = cast(:document_id as text)
            """
        )

        result = self.session.execute(
            statement,
            {
                "document_id": (
                    str(document_id)
                    if not isinstance(document_id, str)
                    else document_id
                ),
            },
        )
        # rowcount lives on CursorResult; getattr keeps type checkers happy.
        return int(getattr(result, "rowcount", 0) or 0)

    def _map_row_to_retrieved_chunk(
        self,
        row: Mapping[str, Any],
    ) -> RetrievedChunk:
        metadata = row.get("metadata_json") or {}
        return RetrievedChunk(
            chunk_id=row["chunk_id"],
            document_id=row["document_id"],
            document_title=row["document_title"],
            content=row["content"],
            score=float(row["score"]),
            source_uri=row.get("source_uri"),
            metadata=metadata,
        )

    def _to_pgvector_literal(self, embedding: list[float]) -> str:
        if not embedding:
            raise ApplicationError(
                message="Embedding vector cannot be empty.",
                code="vector_embedding_empty",
                status_code=422,
            )
        return "[" + ",".join(str(float(value)) for value in embedding) + "]"

    def _to_json(self, metadata: dict[str, str]) -> str:
        import json
        return json.dumps(metadata)

    def ensure_schema(self) -> None:
        table_name = self.settings.vector_store_table_name
        dimension = self.settings.vector_store_dimension

        hnsw_index_sql = (
            f"create index if not exists {table_name}_embedding_idx "
            f"on {table_name} using hnsw (embedding vector_cosine_ops);"
            if dimension <= 2000
            else (
                f"-- HNSW index skipped: dimension {dimension} exceeds "
                "pgvector limit of 2000"
            )
        )

        statements = [
            "create extension if not exists vector;",
            (
                f"create table if not exists {table_name} ("
                "chunk_id text primary key, "
                "knowledge_base_id text not null, "
                "document_id text not null, "
                "document_title text not null, "
                "content text not null, "
                "source_uri text, "
                "metadata_json jsonb default '{{}}'::jsonb, "
                f"embedding vector({dimension}) not null"
                ");"
            ),
            f"create index if not exists {table_name}_kb_idx on {table_name} (knowledge_base_id);",
            hnsw_index_sql,
            (
                f"create index if not exists {table_name}_content_fts_idx "
                f"on {table_name} using gin (to_tsvector('english', content));"
            ),
        ]

        for statement in statements:
            if statement.strip().startswith("--"):
                continue
            self.session.execute(text(statement))

        self.session.commit()