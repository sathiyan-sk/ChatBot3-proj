from types import SimpleNamespace
from typing import cast

from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.knowledge_engine.shared.models import EmbeddedChunk


class _Session:
    def __init__(self):
        self.executions = []
        self.result = _ExecutionResult()

    def execute(self, statement, parameters):
        self.executions.append((str(statement), parameters))
        return self.result


class _ExecutionResult:
    def mappings(self):
        return self

    def all(self):
        return []


def test_pgvector_provider_indexes_many_chunks_with_one_executemany_call():
    session = _Session()
    provider = PgVectorProvider(
        settings=cast(
            Settings,
            SimpleNamespace(vector_store_table_name="document_chunks"),
        ),
        session=cast(Session, session),
    )
    chunks = [
        EmbeddedChunk(
            chunk_id=f"document-1-chunk-{index}",
            content=f"content {index}",
            embedding=[0.1, 0.2],
            metadata={
                "document_id": "document-1",
                "knowledge_base_id": "knowledge-base-1",
                "document_title": "User guide",
                "source_identifier": "guide.pdf",
                "ingestion_version": "3",
            },
        )
        for index in range(3)
    ]

    provider.index_chunks(chunks)

    assert len(session.executions) == 1
    statement, parameters = session.executions[0]
    assert "on conflict (chunk_id, ingestion_version)" in statement.lower()
    assert len(parameters) == 3
    assert parameters[0]["chunk_id"] == "document-1-chunk-0"
    assert parameters[0]["embedding"] == "[0.1,0.2]"
    assert parameters[0]["ingestion_version"] == 3


def test_pgvector_bulk_index_rejects_missing_required_metadata():
    session = _Session()
    provider = PgVectorProvider(
        settings=cast(
            Settings,
            SimpleNamespace(vector_store_table_name="document_chunks"),
        ),
        session=cast(Session, session),
    )

    try:
        provider.index_chunks(
            [
                EmbeddedChunk(
                    chunk_id="chunk-1",
                    content="content",
                    embedding=[0.1],
                    metadata={"document_id": "document-1"},
                )
            ]
        )
    except Exception as exc:
        assert getattr(exc, "code", None) == "vector_index_metadata_invalid"
    else:
        raise AssertionError("Required vector metadata must be validated.")

    assert session.executions == []


def test_retrieval_searches_only_the_published_document_version():
    session = _Session()
    provider = PgVectorProvider(
        settings=cast(
            Settings,
            SimpleNamespace(vector_store_table_name="document_chunks"),
        ),
        session=cast(Session, session),
    )

    provider.similarity_search(
        knowledge_base_id="knowledge-base-1",
        query_embedding=[0.1, 0.2],
        top_k=5,
    )
    provider.keyword_search(
        knowledge_base_id="knowledge-base-1",
        query_text="guide",
        top_k=5,
    )

    assert len(session.executions) == 2
    for statement, _ in session.executions:
        assert "join documents as document" in statement.lower()
        assert "document.ready_version = chunks.ingestion_version" in statement.lower()


def test_obsolete_version_cleanup_is_scoped_to_one_document():
    session = _Session()
    provider = PgVectorProvider(
        settings=cast(
            Settings,
            SimpleNamespace(vector_store_table_name="document_chunks"),
        ),
        session=cast(Session, session),
    )

    provider.delete_obsolete_document_versions(
        document_id="document-1",
        keep_version=4,
    )

    statement, parameters = session.executions[0]
    assert "where document_id = cast(:document_id as text)" in statement.lower()
    assert "ingestion_version <> :keep_version" in statement.lower()
    assert parameters == {"document_id": "document-1", "keep_version": 4}
