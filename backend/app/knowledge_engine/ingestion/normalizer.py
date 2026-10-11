from __future__ import annotations

import re

from app.knowledge_engine.shared.helpers import normalize_whitespace
from app.knowledge_engine.shared.models import (
    DocumentSection,
    NormalizedDocument,
    ParsedDocument,
)


class DocumentNormalizer:
    def normalize(self, document: ParsedDocument) -> NormalizedDocument:
        normalized_sections = [
            normalize_whitespace(section)
            for section in document.sections
            if normalize_whitespace(section)
        ]

        normalized_content = normalize_whitespace(document.content)
        normalized_structured_sections = [
            DocumentSection(
                heading=normalize_whitespace(section.heading),
                content=self._normalize_structured_content(section.content),
                level=section.level,
            )
            for section in document.structured_sections
            if self._normalize_structured_content(section.content)
        ]

        return NormalizedDocument(
            title=normalize_whitespace(document.title) or "Untitled Document",
            content=normalized_content,
            sections=normalized_sections,
            metadata=document.metadata,
            structured_sections=normalized_structured_sections,
        )

    @staticmethod
    def _normalize_structured_content(content: str) -> str:
        return "\n".join(
            re.sub(r"[ \t]+", " ", line).strip()
            for line in content.splitlines()
        ).strip()