"""Unit tests for ``DoclingParsingProvider._resolve_ocr_mode``.

These run without Docling installed: ``DoclingParsingProvider`` imports Docling
lazily (inside ``parse``), and ``_resolve_ocr_mode`` is a pure-Python helper.

The fake enum below deliberately mirrors Docling 2.118.0's ``OcrMode``, which
removed the legacy ``ACCURATE`` member and never had a ``SKIP`` member.
"""

import logging

import pytest
from enum import Enum

from app.core.exceptions import ApplicationError
from app.knowledge_engine.shared.models import RawSource
from app.infrastructure.providers.parsing.docling_provider import (
    DoclingParsingProvider,
)


class _FakeOcrMode(str, Enum):
    """Mirrors docling 2.118.0 OcrMode: ACCURATE / SKIP do not exist."""

    FULL_PAGE = "full_page"
    LAYOUT_REGIONS = "layout_regions"
    PDF_AWARE_LAYOUT_REGIONS = "pdf_aware_layout_regions"
    DEFAULT = "default"


def test_default_resolves_to_default_member():
    result = DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "default")
    assert result is _FakeOcrMode.DEFAULT


def test_known_members_resolve_by_name():
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "full_page")
        is _FakeOcrMode.FULL_PAGE
    )
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "layout_regions")
        is _FakeOcrMode.LAYOUT_REGIONS
    )
    assert (
        DoclingParsingProvider._resolve_ocr_mode(
            _FakeOcrMode, "pdf_aware_layout_regions"
        )
        is _FakeOcrMode.PDF_AWARE_LAYOUT_REGIONS
    )


def test_legacy_accurate_does_not_raise_and_falls_back_to_default(caplog):
    # Regression: OcrMode.ACCURATE was removed in docling 2.118.0; the old
    # eager dict literal crashed here even for DOCLING_OCR_MODE=default.
    with caplog.at_level(logging.WARNING):
        result = DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "accurate")
    assert result is _FakeOcrMode.DEFAULT
    assert "unavailable" in caplog.text.lower()


def test_legacy_skip_does_not_raise_and_falls_back_to_default(caplog):
    # Regression: OcrMode.SKIP was never a 2.118.0 member either.
    with caplog.at_level(logging.WARNING):
        result = DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "skip")
    assert result is _FakeOcrMode.DEFAULT
    assert "unavailable" in caplog.text.lower()


def test_unknown_mode_does_not_raise_and_falls_back_to_default(caplog):
    with caplog.at_level(logging.WARNING):
        result = DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "bogus")
    assert result is _FakeOcrMode.DEFAULT
    assert "unavailable" in caplog.text.lower()


def test_empty_and_whitespace_inputs_fall_back_to_default():
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "")
        is _FakeOcrMode.DEFAULT
    )
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "   ")
        is _FakeOcrMode.DEFAULT
    )


def test_case_insensitive_lookup():
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "DEFAULT")
        is _FakeOcrMode.DEFAULT
    )
    assert (
        DoclingParsingProvider._resolve_ocr_mode(_FakeOcrMode, "Full_Page")
        is _FakeOcrMode.FULL_PAGE
    )


def test_default_dpi_maps_to_intended_144dpi_scale():
    # The .env.example operating point (144 DPI) must map to scale 2.0, which
    # reproduces Docling's onnxruntime default for the *selective* OCR path and
    # is BELOW docling's full-path default of scale 3.0 (= 216 DPI).
    assert DoclingParsingProvider._resolve_ocr_image_scale(None, 144) == 2.0
    assert DoclingParsingProvider._resolve_ocr_image_scale("", 144) == 2.0


@pytest.mark.parametrize(
    "dpi,expected",
    [
        (72, 1.0),    # 72 DPI == scale 1.0 (minimum, not downscaled)
        (108, 1.5),
        (144, 2.0),
        (216, 3.0),   # == docling's hardcoded default (216 DPI)
    ],
)
def test_dpi_to_scale_mapping(dpi, expected):
    assert DoclingParsingProvider._resolve_ocr_image_scale(str(dpi), 144) == expected


def test_dpi_below_one_dpi_is_clamped_to_one_to_avoid_sub_72_dpi():
    # 36/72 == 0.5 -> must NOT downscale below 72 DPI (recognition degrades).
    assert DoclingParsingProvider._resolve_ocr_image_scale("36", 144) == 1.0


def test_invalid_dpi_falls_back_to_default_with_warning(caplog):
    with caplog.at_level(logging.WARNING):
        scale = DoclingParsingProvider._resolve_ocr_image_scale("not-a-number", 144)
    assert scale == 2.0
    assert "invalid" in caplog.text.lower()


# ---------------------------------------------------------------------------
# Source extension derivation + parse() format guard
# ---------------------------------------------------------------------------


def test_prewarm_probe_without_pdf_suffix_collapses_to_unsupported_extension():
    # Regression: the prewarm script originally passed "prewarm:docling-cache"
    # (no ".pdf" suffix). With no dot, rsplit keeps the entire identifier as
    # the "extension", so the parser rejected it as docling_format_unsupported.
    assert (
        DoclingParsingProvider._resolve_source_extension("prewarm:docling-cache")
        == "prewarm:docling-cache"
    )


def test_prewarm_probe_with_pdf_suffix_resolves_to_pdf():
    # The fix: the synthetic probe now carries a trailing .pdf.
    assert (
        DoclingParsingProvider._resolve_source_extension("prewarm:docling-cache.pdf")
        == "pdf"
    )


def test_extension_is_case_insensitive():
    assert DoclingParsingProvider._resolve_source_extension("scan.PDF") == "pdf"
    assert DoclingParsingProvider._resolve_source_extension("scan.DocX") == "docx"


@pytest.mark.parametrize(
    "identifier,expected",
    [
        ("scan.png", "png"),
        ("scan.jpg", "jpg"),
        ("uploads/user/report.pdf", "pdf"),
        ("noext", "noext"),
        ("", "document"),  # empty identifier falls back to the provider default name
    ],
)
def test_resolve_source_extension(identifier, expected):
    assert DoclingParsingProvider._resolve_source_extension(identifier) == expected


def test_parse_rejects_prewarm_probe_without_extension():
    # Exercises the parse() guard only (raises before the lazy Docling import /
    # pymupdf, so it runs without native deps installed).
    provider = DoclingParsingProvider()
    source = RawSource(
        source_type="pdf",
        source_identifier="prewarm:docling-cache",  # the original, buggy value
        content_bytes=b"%PDF-1.4 synthetic prewarm page",
    )
    with pytest.raises(ApplicationError) as exc:
        provider.parse(source)
    assert exc.value.code == "docling_format_unsupported"
    assert "prewarm:docling-cache" in exc.value.message


def test_parse_rejects_disallowed_extension():
    provider = DoclingParsingProvider()
    source = RawSource(
        source_type="pdf",
        source_identifier="scan.png",
        content_bytes=b"\x89PNG\r\n\x1a\n synthetic bytes",
    )
    with pytest.raises(ApplicationError) as exc:
        provider.parse(source)
    assert exc.value.code == "docling_format_unsupported"
    assert ".png" in exc.value.message
