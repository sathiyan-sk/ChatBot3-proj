from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO

from app.core.exceptions import ApplicationError
from app.knowledge_engine.ingestion.parsers.base import DocumentParser
from app.knowledge_engine.shared.helpers import normalize_whitespace
from app.knowledge_engine.shared.models import ParsedDocument, RawSource


@dataclass(slots=True)
class CsvDocumentParser(DocumentParser):
    def parse(self, source: RawSource) -> ParsedDocument:
        if source.content_text is not None:
            content = source.content_text
        elif source.content_bytes is not None:
            try:
                content = source.content_bytes.decode("utf-8-sig")
            except UnicodeDecodeError as exc:
                raise ApplicationError(
                    message="CSV documents must use UTF-8 encoding.",
                    code="csv_encoding_unsupported",
                    status_code=422,
                ) from exc
        else:
            content = ""

        content = content.lstrip("\ufeff")
        try:
            rows = list(csv.reader(StringIO(content), strict=True))
        except csv.Error as exc:
            raise ApplicationError(
                message=f"CSV parsing failed: {exc}",
                code="csv_parse_failed",
                status_code=422,
            ) from exc

        rows = [row for row in rows if any(cell.strip() for cell in row)]
        if not rows:
            raise ApplicationError(
                message="CSV document content is empty.",
                code="csv_content_empty",
                status_code=422,
            )

        headers = [
            normalize_whitespace(value) or f"Column {index + 1}"
            for index, value in enumerate(rows[0])
        ]
        sections: list[str] = []
        for row in rows[1:]:
            fields = [
                f"{headers[index]}: {normalize_whitespace(value)}"
                for index, value in enumerate(row)
                if index < len(headers) and normalize_whitespace(value)
            ]
            if fields:
                sections.append("\n".join(fields))

        if not sections:
            sections = ["CSV columns: " + ", ".join(headers)]

        source_name = source.source_identifier.rsplit("/", 1)[-1] or "document.csv"
        title = source.metadata.get("document_title") or source_name
        return ParsedDocument(
            title=title,
            content="\n\n".join(sections),
            sections=sections,
            metadata=dict(source.metadata),
        )