from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class CreateDocumentCommand:
    knowledge_base_id: str
    title: str
    description: str | None
    source_type: str
    source_uri: str
    status: str = "pending"


@dataclass(slots=True, frozen=True)
class UpdateDocumentCommand:
    document_id: str
    title: str
    description: str | None
    status: str


@dataclass(slots=True, frozen=True)
class MarkDocumentProcessingCommand:
    document_id: str


@dataclass(slots=True, frozen=True)
class MarkDocumentReadyCommand:
    document_id: str


@dataclass(slots=True, frozen=True)
class MarkDocumentFailedCommand:
    document_id: str
    failure_reason: str | None = None


@dataclass(slots=True, frozen=True)
class ArchiveDocumentCommand:
    document_id: str


@dataclass(slots=True, frozen=True)
class DeleteDocumentCommand:
    document_id: str
