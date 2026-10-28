from __future__ import annotations

import pytest

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.parsing import ParsingContract
from app.knowledge_engine.ingestion.parsers.quality_aware_document_parser import (
    QualityAwareDocumentParser,
)
from app.knowledge_engine.shared.models import (
    ExtractedPage,
    ParsedDocument,
    RawSource,
)


class _FakeFastParser(ParsingContract):
    """Stand-in for PyMuPDF: either returns a parsed doc or raises."""

    def __init__(self, result: ParsedDocument | None = None, code: str | None = None):
        self._result = result
        self._code = code
        self.parse_call_count = 0

    def parse(self, source: RawSource) -> ParsedDocument:
        self.parse_call_count += 1
        if self._code is not None:
            raise ApplicationError(
                message="fast parser failure",
                code=self._code,
                status_code=422,
            )
        assert self._result is not None
        return self._result


class _FakeOcrParser(ParsingContract):
    """Stand-in for Docling: records full-parse vs image-page OCR calls."""

    def __init__(self, full_result: ParsedDocument | None = None):
        self._full_result = full_result
        self.parse_call_count = 0
        self.parse_image_pages_calls: list[tuple[RawSource, list[int]]] = []
        self.image_pages_results: list[str] = []

    def parse(self, source: RawSource) -> ParsedDocument:
        self.parse_call_count += 1
        assert self._full_result is not None
        return self._full_result

    def parse_image_pages(self, source: RawSource, page_numbers: list[int]) -> list[str]:
        self.parse_image_pages_calls.append((source, list(page_numbers)))
        return list(self.image_pages_results)


def _source() -> RawSource:
    return RawSource(
        source_type="file",
        source_identifier="doc.pdf",
        content_bytes=b"%PDF-1.4 fake document bytes",
    )


def _pages(spec: dict[int, bool]) -> list[ExtractedPage]:
    return [
        ExtractedPage(
            page_number=n,
            text=("text " * n if has else ""),
            has_selectable_text=has,
        )
        for n, has in sorted(spec.items())
    ]


def test_fast_path_text_pdf_skips_ocr():
    fast = _FakeFastParser(
        result=ParsedDocument(
            title="doc.pdf",
            content="Knowledge base PDF fixture",
            sections=["Knowledge base PDF fixture"],
            metadata={
                "page_count": "1",
                "pages_with_selectable_text": "1",
                "selectable_page_ratio": "1.00",
            },
            page_results=_pages({1: True}),
        )
    )
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(title="d", content="OCR", sections=[])
    )
    parser = QualityAwareDocumentParser(
        fast_parser=fast, ocr_parser=ocr, selectable_ratio_threshold=0.5
    )

    parsed = parser.parse(_source())

    assert fast.parse_call_count == 1
    assert ocr.parse_call_count == 0
    assert ocr.parse_image_pages_calls == []
    assert parsed.content == "Knowledge base PDF fixture"
    assert parsed.metadata["parser"] == "pymupdf"
    assert parsed.metadata["ocr_applied"] == "false"
    assert parsed.page_results == _pages({1: True})


def test_scanned_pdf_falls_back_to_full_docling_ocr():
    fast = _FakeFastParser(code="pdf_text_not_found")
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(
            title="scanned.pdf",
            content="OCR recovered text",
            sections=["OCR recovered text"],
        )
    )
    parser = QualityAwareDocumentParser(fast_parser=fast, ocr_parser=ocr)

    parsed = parser.parse(_source())

    assert fast.parse_call_count == 1
    assert ocr.parse_call_count == 1
    assert parsed.content == "OCR recovered text"
    assert parsed.metadata["parser"] == "docling"
    assert parsed.metadata["ocr_applied"] == "true"


def test_mixed_doc_selective_ocr_preserves_text_without_duplication():
    fast = _FakeFastParser(
        result=ParsedDocument(
            title="mixed.pdf",
            content="Selectable text remains indexable",
            sections=["Selectable text remains indexable"],
            metadata={
                "page_count": "2",
                "pages_with_selectable_text": "1",
                "selectable_page_ratio": "0.50",
            },
            page_results=_pages({1: True, 2: False}),
        )
    )
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(title="d", content="X", sections=[])
    )
    ocr.image_pages_results = ["Text only available as image pixels"]
    parser = QualityAwareDocumentParser(
        fast_parser=fast, ocr_parser=ocr, selectable_ratio_threshold=0.9
    )

    parsed = parser.parse(_source())

    # Full Docling parse is NOT used (only selective image-page OCR).
    assert ocr.parse_call_count == 0
    # Only the image-only page is OCR'd -> no duplication of the text page.
    assert ocr.parse_image_pages_calls == [(_source(), [2])]
    # Page 1 (selectable) comes before page 2 (OCR'd) -> correct page order.
    assert parsed.content.index("text") < parsed.content.index("image pixels")
    assert parsed.content.count("Text only available as image pixels") == 1
    assert "Selectable text remains indexable" not in parsed.content
    assert parsed.metadata["parser"] == "pymupdf"
    assert parsed.metadata["ocr_applied"] == "selective"


def test_minimal_selectable_text_still_triggers_selective_ocr_of_images():
    # Issue A: a page carrying only a page-number marker counts as selectable
    # text, but the document is mostly images -> the image-only pages must be
    # OCR'd and re-interleaved in their original page order.
    page_results = [
        ExtractedPage(page_number=1, text="Page one selectable", has_selectable_text=True),
        ExtractedPage(page_number=2, text="", has_selectable_text=False),
        ExtractedPage(page_number=3, text="", has_selectable_text=False),
        ExtractedPage(page_number=4, text="", has_selectable_text=False),
        ExtractedPage(page_number=5, text="", has_selectable_text=False),
    ]
    fast = _FakeFastParser(
        result=ParsedDocument(
            title="minimal.pdf",
            content="Page one selectable",
            sections=["Page one selectable"],
            metadata={
                "page_count": "5",
                "pages_with_selectable_text": "1",
                "selectable_page_ratio": "0.20",
            },
            page_results=page_results,
        )
    )
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(title="d", content="X", sections=[])
    )
    ocr.image_pages_results = ["OCR page 2", "OCR page 3", "OCR page 4", "OCR page 5"]
    parser = QualityAwareDocumentParser(
        fast_parser=fast, ocr_parser=ocr, selectable_ratio_threshold=0.5
    )

    parsed = parser.parse(_source())

    assert ocr.parse_call_count == 0
    assert ocr.parse_image_pages_calls == [(_source(), [2, 3, 4, 5])]
    # All five pages present, in order: page1 text, then page2..5 OCR text.
    tokens = [
        "Page one selectable",
        "OCR page 2",
        "OCR page 3",
        "OCR page 4",
        "OCR page 5",
    ]
    positions = [parsed.content.index(t) for t in tokens]
    assert positions == sorted(positions)
    assert parsed.metadata["ocr_applied"] == "selective"


def test_selective_ocr_failure_on_a_page_escalates_to_full_ocr():
    # Issue B: OCR of an image-only page returns empty -> the orchestrator must
    # NOT publish an incomplete document; it escalates to a full Docling pass.
    fast = _FakeFastParser(
        result=ParsedDocument(
            title="mixed.pdf",
            content="Page one text",
            sections=["Page one text"],
            metadata={
                "page_count": "2",
                "pages_with_selectable_text": "1",
                "selectable_page_ratio": "0.50",
            },
            page_results=_pages({1: True, 2: False}),
        )
    )
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(
            title="mixed.pdf",
            content="Full Docling OCR text for the whole document",
            sections=["Full Docling OCR text for the whole document"],
        )
    )
    ocr.image_pages_results = [""]  # page 2 OCR failed -> empty
    parser = QualityAwareDocumentParser(
        fast_parser=fast, ocr_parser=ocr, selectable_ratio_threshold=0.9
    )

    parsed = parser.parse(_source())

    # Selective OCR was attempted...
    assert ocr.parse_image_pages_calls == [(_source(), [2])]
    # ...and, having produced no text for the image page, the full fallback ran.
    assert ocr.parse_call_count == 1
    assert parsed.content == "Full Docling OCR text for the whole document"
    assert parsed.metadata["parser"] == "docling"
    assert parsed.metadata["ocr_applied"] == "true"


def test_other_fast_parser_errors_are_not_swallowed():
    fast = _FakeFastParser(code="pdf_extraction_failed")
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(title="d", content="x", sections=[])
    )
    parser = QualityAwareDocumentParser(fast_parser=fast, ocr_parser=ocr)

    with pytest.raises(ApplicationError) as exc_info:
        parser.parse(_source())

    assert exc_info.value.code == "pdf_extraction_failed"
    assert ocr.parse_call_count == 0


def test_fast_path_with_ratio_below_threshold_but_no_image_pages():
    fast = _FakeFastParser(
        result=ParsedDocument(
            title="low.pdf",
            content="sparse text",
            sections=["sparse text"],
            metadata={
                "page_count": "1",
                "pages_with_selectable_text": "1",
                "selectable_page_ratio": "0.10",
            },
            page_results=_pages({1: True}),
        )
    )
    ocr = _FakeOcrParser(
        full_result=ParsedDocument(title="d", content="x", sections=[])
    )
    parser = QualityAwareDocumentParser(
        fast_parser=fast, ocr_parser=ocr, selectable_ratio_threshold=0.5
    )

    parsed = parser.parse(_source())

    assert ocr.parse_call_count == 0
    assert ocr.parse_image_pages_calls == []
    assert parsed.metadata["ocr_applied"] == "false"


def test_missing_content_raises_before_any_parsing():
    fast = _FakeFastParser()
    ocr = _FakeOcrParser()
    parser = QualityAwareDocumentParser(fast_parser=fast, ocr_parser=ocr)

    with pytest.raises(ApplicationError) as exc_info:
        parser.parse(
            RawSource(
                source_type="file",
                source_identifier="doc.pdf",
                content_bytes=None,
            )
        )

    assert exc_info.value.code == "document_content_missing"
    assert fast.parse_call_count == 0
    assert ocr.parse_call_count == 0

