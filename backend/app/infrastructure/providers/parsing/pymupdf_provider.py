from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

try:
    import pymupdf
except ImportError:  # pragma: no cover - optional dependency
    pymupdf = None

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.parsing import (
    ParsingContract,
)
from app.knowledge_engine.shared.helpers import (
    normalize_whitespace,
    split_text_into_paragraphs,
)
from app.knowledge_engine.shared.models import (
    ParsedDocument,
    RawSource,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PyMuPDFParsingProvider(ParsingContract):
    def parse(
        self,
        source: RawSource,
    ) -> ParsedDocument:
        if pymupdf is None:
            raise ApplicationError(
                message="PyMuPDF is not installed. Install the PDF parser dependency to process PDF documents.",
                code="pdf_dependency_missing",
                status_code=503,
            )

        if source.content_bytes is None:
            raise ApplicationError(
                message="PDF content is missing.",
                code="pdf_content_missing",
                status_code=422,
            )

        try:
            with pymupdf.open(
                stream=BytesIO(
                    source.content_bytes,
                ),
                filetype="pdf",
            ) as pdf:
                page_text: list[str] = []
                pages_with_selectable_text = 0
                for page in pdf:
                    text = page.get_text(
                        "text",
                        sort=True,
                    )
                    if isinstance(text, str) and text.strip():
                        page_text.append(text)
                        pages_with_selectable_text += 1
                page_count = pdf.page_count

        except Exception as exc:
            raise ApplicationError(
                message=f"PDF extraction failed: {exc}",
                code="pdf_extraction_failed",
                status_code=422,
            ) from exc

        extracted_text = "\n\n".join(page_text)
        logger.info(
            (
                "PyMuPDF selectable-text extraction completed: "
                "pages=%d, pages_with_selectable_text=%d, "
                "extracted_characters=%d"
            ),
            page_count,
            pages_with_selectable_text,
            len(extracted_text),
            extra={
                "source_type": "pdf",
                "page_count": page_count,
                "pages_with_selectable_text": pages_with_selectable_text,
                "extracted_characters": len(extracted_text),
            },
        )

        normalized_text = normalize_whitespace(
            extracted_text,
        )

        if not normalized_text:
            logger.warning(
                (
                    "PDF contains no selectable text; image content is "
                    "not OCR'd: pages=%d, pages_with_selectable_text=%d, "
                    "extracted_characters=%d"
                ),
                page_count,
                pages_with_selectable_text,
                len(extracted_text),
                extra={"page_count": page_count},
            )
            raise ApplicationError(
                message=(
                    "No selectable text was found in "
                    "the PDF. It may be scanned."
                ),
                code="pdf_text_not_found",
                status_code=422,
            )

        paragraphs = split_text_into_paragraphs(
            normalized_text,
        )

        source_name = (
            source.source_identifier.rsplit(
                "/",
                1,
            )[-1]
            or "document.pdf"
        )

        title = (
            source.metadata.get("document_title")
            or source_name
        )

        return ParsedDocument(
            title=title,
            content=normalized_text,
            sections=paragraphs or [normalized_text],
            metadata={
                **source.metadata,
                "parser": "pymupdf",
                "page_count": str(page_count),
                "pages_with_selectable_text": str(
                    pages_with_selectable_text
                ),
            },
        )