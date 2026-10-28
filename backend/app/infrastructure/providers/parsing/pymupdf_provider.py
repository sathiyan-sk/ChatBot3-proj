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
    ExtractedPage,
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
                page_results: list[ExtractedPage] = []
                for index, page in enumerate(pdf, start=1):
                    text = self._extract_page_text(page)
                    has_text = bool(text and text.strip())
                    page_results.append(
                        ExtractedPage(
                            page_number=index,
                            text=text,
                            has_selectable_text=has_text,
                        )
                    )
                page_count = len(page_results)

        except Exception as exc:
            raise ApplicationError(
                message=f"PDF extraction failed: {exc}",
                code="pdf_extraction_failed",
                status_code=422,
            ) from exc

        extracted_text = "\n\n".join(
            page.text for page in page_results if page.has_selectable_text
        )
        pages_with_selectable_text = sum(
            1 for page in page_results if page.has_selectable_text
        )
        selectable_page_ratio = (
            pages_with_selectable_text / page_count if page_count else 0.0
        )
        logger.info(
            (
                "PyMuPDF selectable-text extraction completed: "
                "pages=%d, pages_with_selectable_text=%d, "
                "extracted_characters=%d, selectable_page_ratio=%.2f"
            ),
            page_count,
            pages_with_selectable_text,
            len(extracted_text),
            selectable_page_ratio,
            extra={
                "source_type": "pdf",
                "page_count": page_count,
                "pages_with_selectable_text": pages_with_selectable_text,
                "extracted_characters": len(extracted_text),
                "selectable_page_ratio": round(selectable_page_ratio, 2),
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
                    "extracted_characters=%d, selectable_page_ratio=0.00"
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
                "selectable_page_ratio": f"{selectable_page_ratio:.2f}",
            },
            page_results=page_results,
        )

    @staticmethod
    def _extract_page_text(page) -> str:
        """Recover selectable text from a single page.

        ``get_text("text", sort=True)`` can return an empty string for pages
        whose text is selectable in a PDF viewer (e.g. fonts lacking a
        ToUnicode mapping) — a known PyMuPDF edge case that produced the
        false "No selectable text was found" rejection. This helper tries a
        sequence of extraction modes so a text-based PDF is never falsely
        classified as scanned/image-only.
        """
        text = page.get_text("text", sort=True)
        if text and text.strip():
            return text

        text = page.get_text("text")
        if text and text.strip():
            return text

        text = " ".join(word[4] for word in page.get_text("words"))
        if text and text.strip():
            return text

        blocks = page.get_text("blocks")
        if isinstance(blocks, (list, tuple)):
            text = " ".join(
                str(block[4])
                for block in blocks
                if len(block) > 4 and block[4]
            )
        if text and text.strip():
            return text

        return ""