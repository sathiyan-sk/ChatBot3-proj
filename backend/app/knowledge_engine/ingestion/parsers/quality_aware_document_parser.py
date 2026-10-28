from __future__ import annotations

import logging
from dataclasses import dataclass

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.parsing import ParsingContract
from app.knowledge_engine.ingestion.parsers.base import DocumentParser
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
class QualityAwareDocumentParser(DocumentParser):
    """Quality-aware PDF routing orchestrator.

    Strategy:
    1. Fast path - PyMuPDF extracts the selectable text layer (no OCR). This
       fixes the false "No selectable text was found" rejection on text-based
       PDFs and avoids OCR on documents that already have selectable text.
    2. Selective OCR - when a document is mostly image-based but has a little
       recoverable text, only the image-only pages are rasterized and OCR'd
       (via Docling). Selectable text is preserved and the image-only pages
       are NOT reprocessed, so nothing is duplicated.
    3. Full OCR fallback - when PyMuPDF finds no selectable text at all (a
       fully scanned PDF it would normally reject), Docling runs a full OCR
       pass instead of failing the ingestion.

    Page-level results (``ExtractedPage``) drive every decision, so no second
    full extraction is required on the fast path.
    """

    fast_parser: ParsingContract
    ocr_parser: ParsingContract
    selectable_ratio_threshold: float = 0.5

    def parse(self, source: RawSource) -> ParsedDocument:
        if source.content_bytes is None:
            raise ApplicationError(
                message="Document content is missing.",
                code="document_content_missing",
                status_code=422,
            )

        fast = self._extract_selectable_text(source)
        page_results = fast.page_results if fast is not None else []

        # 3. Fully scanned document -> full Docling OCR fallback.
        if fast is None:
            logger.info(
                "QualityAware routing: no selectable text found; "
                "falling back to full-document OCR."
            )
            parsed = self.ocr_parser.parse(source)
            return self._with_ocr_metadata(parsed, ocr_applied="true")

        text_pages = [page for page in page_results if page.has_selectable_text]
        image_only_pages = [
            page.page_number
            for page in page_results
            if not page.has_selectable_text
        ]
        selectable_ratio = (
            len(text_pages) / len(page_results) if page_results else 0.0
        )

        # 1. Fast path: enough selectable text and nothing substantial to OCR.
        if not image_only_pages or (
            selectable_ratio >= self.selectable_ratio_threshold
        ):
            metadata = {
                **fast.metadata,
                "parser": "pymupdf",
                "ocr_applied": "false",
            }
            logger.info(
                "QualityAware routing: PyMuPDF fast path "
                "(selectable_ratio=%.2f, ocr_applied=false).",
                selectable_ratio,
            )
            return ParsedDocument(
                title=fast.title,
                content=fast.content,
                sections=fast.sections,
                metadata=metadata,
                structured_sections=fast.structured_sections,
                page_results=page_results,
            )

        # 2. Mostly image-based: preserve each page's selectable text and OCR
        #    ONLY the image-only pages, interleaving in the original page order
        #    so pages are neither duplicated nor dropped.
        ocr_texts = self._ocr_image_only_pages(source, image_only_pages)
        ocr_by_page = dict(zip(image_only_pages, ocr_texts))
        if any(not ocr_by_page.get(page, "") for page in image_only_pages):
            # Selective OCR could not recover every image-only page -> escalate
            # to a full Docling pass so the document is not published incomplete.
            logger.info(
                "QualityAware routing: selective OCR incomplete; "
                "escalating to full-document OCR."
            )
            parsed = self.ocr_parser.parse(source)
            return self._with_ocr_metadata(parsed, ocr_applied="true")

        ordered_texts: list[str] = []
        for page in page_results:
            if page.has_selectable_text:
                ordered_texts.append(page.text)
            else:
                ordered_texts.append(ocr_by_page[page.page_number])
        content = normalize_whitespace("\n\n".join(ordered_texts))
        sections = split_text_into_paragraphs(content) or [content]
        metadata = {
            **fast.metadata,
            "parser": "pymupdf",
            "ocr_applied": "selective",
        }
        logger.info(
            "QualityAware routing: selective OCR applied to "
            "image-only pages=%d; pages kept in order, no duplication.",
            len(image_only_pages),
        )
        return ParsedDocument(
            title=fast.title,
            content=content,
            sections=sections,
            metadata=metadata,
            structured_sections=fast.structured_sections,
            page_results=page_results,
        )

    def _extract_selectable_text(
        self, source: RawSource
    ) -> ParsedDocument | None:
        """Run the fast parser; return None when it rejects a scanned PDF."""
        try:
            return self.fast_parser.parse(source)
        except ApplicationError as exc:
            if exc.code != "pdf_text_not_found":
                raise
            logger.info(
                "QualityAware routing: fast parser reported "
                "pdf_text_not_found (source=%s).",
                source.source_identifier,
            )
            return None

    def _ocr_image_only_pages(
        self, source: RawSource, page_numbers: list[int]
    ) -> list[str]:
        """OCR only the image-only pages, in the order requested.

        Returns one OCR text per requested page (aligned 1:1 with
        ``page_numbers``). An empty string marks a page whose OCR yielded
        nothing, which lets the caller escalate to a full Docling pass so a
        document is never published with missing pages.
        """
        ocr_parser = self.ocr_parser
        if not hasattr(ocr_parser, "parse_image_pages"):
            logger.warning(
                "QualityAware routing: ocr_parser does not implement "
                "parse_image_pages; treating image-only pages as empty."
            )
            return [""] * len(page_numbers)
        try:
            results = ocr_parser.parse_image_pages(
                source, page_numbers
            )  # type: ignore[attr-defined]
        except ApplicationError as exc:
            logger.warning(
                "QualityAware routing: selective page OCR failed "
                "(code=%s); escalating to full OCR.",
                exc.code,
            )
            return [""] * len(page_numbers)
        texts = list(results)
        if len(texts) != len(page_numbers):
            logger.warning(
                "QualityAware routing: selective OCR returned %d "
                "results for %d requested pages.",
                len(texts),
                len(page_numbers),
            )
            texts = (texts + [""] * len(page_numbers))[: len(page_numbers)]
        return texts

    def _with_ocr_metadata(
        self, parsed: ParsedDocument, *, ocr_applied: str
    ) -> ParsedDocument:
        return ParsedDocument(
            title=parsed.title,
            content=parsed.content,
            sections=parsed.sections,
            metadata={
                **parsed.metadata,
                "parser": "docling",
                "ocr_applied": ocr_applied,
            },
            structured_sections=parsed.structured_sections,
            page_results=getattr(parsed, "page_results", []) or [],
        )
