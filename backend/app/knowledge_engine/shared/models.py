from __future__ import annotations

from dataclasses import dataclass, field

from app.knowledge_engine.contracts.llm import LlmGenerationResult


@dataclass(slots=True, frozen=True)
class RawSource:
    source_type: str
    source_identifier: str
    content_text: str | None = None
    content_bytes: bytes | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class ParsedDocument:
    title: str
    content: str
    sections: list[str]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class NormalizedDocument:
    title: str
    content: str
    sections: list[str]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class EmbeddedChunk:
    chunk_id: str
    content: str
    embedding: list[float]
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    content: str
    score: float
    source_uri: str | None
    metadata: dict[str, str]


@dataclass(slots=True, frozen=True)
class Citation:
    document_id: str
    document_title: str
    chunk_id: str
    source_uri: str | None


@dataclass(slots=True, frozen=True)
class KnowledgeIngestionPipelineRequest:
    document_id: str
    knowledge_base_id: str
    source_type: str
    source_path: str
    source_identifier: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class KnowledgeIngestionPipelineResult:
    document_id: str
    knowledge_base_id: str
    chunk_count: int
    indexed_chunk_ids: list[str]
    document_title: str
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True, frozen=True)
class QuestionAnsweringPipelineRequest:
    application_id: str
    knowledge_base_id: str
    query_text: str
    conversation_id: str
    messages: list[dict[str, str]]
    top_k: int = 5
    max_context_messages: int = 12
    llm_temperature: float | None = None
    prompt_system_template: str | None = None
    request_id: str | None = None


@dataclass(slots=True, frozen=True)
class QuestionAnsweringPipelineResult:
    answer_text: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    llm_generation: LlmGenerationResult | None = None