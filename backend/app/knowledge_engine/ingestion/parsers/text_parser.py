from __future__ import annotations

from app.knowledge_engine.shared.helpers import (
    normalize_whitespace,
    split_text_into_paragraphs,
)
from app.knowledge_engine.shared.models import (
    ParsedDocument,
    RawSource,
)
from app.knowledge_engine.ingestion.parsers.base import DocumentParser


class TextDocumentParser(DocumentParser):
    """Parser for plain-text style sources (txt, md, json, csv-as-text).

    The bytes are decoded as UTF-8; decoding failures fall back to a
    lossy decode so ingestion never hard-fails on stray bytes.
    """

    def parse(self, source: RawSource) -> ParsedDocument:
        if source.content_text is not None:
            extracted_text = source.content_text
        elif source.content_bytes is not None:
            try:
                extracted_text = source.content_bytes.decode("utf-8")
            except UnicodeDecodeError:
                extracted_text = source.content_bytes.decode(
                    "utf-8",
                    errors="replace",
                )
        else:
            extracted_text = ""

        normalized_text = normalize_whitespace(extracted_text)

        if not normalized_text:
            from app.core.exceptions import ApplicationError

            raise ApplicationError(
                message="Text document content is empty.",
                code="text_parsed_content_empty",
                status_code=422,
            )

        paragraphs = split_text_into_paragraphs(normalized_text)

        source_name = (
            source.source_identifier.rsplit("/", 1)[-1]
            or "document"
        )

        title = (
            source.metadata.get("document_title")
            or source_name
            or "Untitled Document"
        )

        return ParsedDocument(
            title=title,
            content=normalized_text,
            sections=paragraphs or [normalized_text],
            metadata=dict(source.metadata),
        )