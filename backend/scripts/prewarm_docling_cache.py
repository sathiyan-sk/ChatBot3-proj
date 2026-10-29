"""One-shot prewarm for Docling's OCR/model cache on a fresh Linux server.

Run this ONCE, against the shared cache volume, before routing user traffic:

    cd /srv/.../backend
    HF_HOME=/var/lib/docling/hf_cache \\
    DOCLING_ARTIFACTS_PATH=/var/lib/docling/artifacts \\
    .venv/bin/python scripts/prewarm_docling_cache.py

It feeds a tiny synthetic image-only PDF through ``DoclingParsingProvider`` — the
exact same code path user uploads take (do_ocr=True, ocr_mode=DEFAULT, and the
same OCR raster ``scale`` derived from ``DOCLING_OCR_IMAGE_DPI``) — so it both
exercises the scale fix end-to-end and confirms the shared cache is wired.

Cache provisioning model
------------------------
* With ``DOCLING_ARTIFACTS_PATH`` set, Docling treats that directory as an
  authoritative, pre-populated location and will NOT download into it. You must
  prefetch the RapidOCR onnx checkpoints before first use:

      .venv/bin/docling-tools models download rapidocr \
          --rapidocr-backend-lang onnxruntime:en -o "$DOCLING_ARTIFACTS_PATH"

  which materializes the ``RapidOcr/PP-OCRv*.onnx`` weights the parse then looks
  for under ``<artifacts_path>/RapidOcr``. Run it ONCE on the shared volume.
* If ``DOCLING_ARTIFACTS_PATH`` is left unset, Docling falls back to its default
  cache (under ``$HF_HOME``) and auto-downloads on first OCR — but that makes the
  first real Aadhaar pay the download time (the 300s timeout). Prefer the
  explicit pre-fetch above for a warm worker boot.

No real customer document is needed and no data leaves the host.
"""
from __future__ import annotations

import io
import os
import sys

import pymupdf  # PyMuPDF; available wherever Docling OCR runs

from app.knowledge_engine.shared.models import RawSource
from app.infrastructure.providers.parsing.docling_provider import DoclingParsingProvider


def _tiny_image_only_pdf() -> bytes:
    """A 1-page PDF with *no* text layer — forces the Docling OCR path to run."""
    doc = pymupdf.open()
    page = doc.new_page(width=300, height=300)
    # Gray shapes (not selectable text) so PyMuPDF fast path yields 0 chars
    # and Docling OCR is exercised end-to-end.
    page.draw_rect(rect=pymupdf.Rect(10, 10, 290, 290),
                    color=(0.2, 0.2, 0.2), fill=(0.55, 0.55, 0.55))
    page.draw_circle(center=(150, 150), radius=60, color=(0.1, 0.1, 0.1),
                     fill=(0.85, 0.85, 0.85))
    data = doc.tobytes()
    doc.close()
    return data


def main() -> int:
    pdf_bytes = _tiny_image_only_pdf()
    print(f"prewarm: synthetic image-only PDF built, bytes={len(pdf_bytes)}")

    provider = DoclingParsingProvider()  # defaults: do_ocr=True, ocr_mode="default"
    source = RawSource(
        source_type="pdf",
        source_identifier="prewarm:docling-cache.pdf",
        content_bytes=pdf_bytes,
        metadata={},
    )
    parsed = provider.parse(source)
    sections = len(parsed.sections) if getattr(parsed, "sections", None) else 0
    preview = (parsed.markdown or "")[:120].replace("\n", " ")
    print(f"prewarm: OK status=success sections={sections} "
          f"markdown_chars={len(parsed.markdown)} preview={preview!r}")

    artifacts = os.getenv("DOCLING_ARTIFACTS_PATH", "")
    hf_home = os.getenv("HF_HOME", "")
    print(f"prewarm: cache_dir_exists={bool(artifacts) and os.path.isdir(artifacts)} "
          f"hf_cache_dir_exists={bool(hf_home) and os.path.isdir(hf_home)} "
          f"artifacts_path={artifacts!r} hf_home={hf_home!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
