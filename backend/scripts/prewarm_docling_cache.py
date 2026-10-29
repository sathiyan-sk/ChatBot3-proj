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

  For scanned/image-only PDFs (e.g. Aadhaar cards), also set DOCLING_SKIP_LAYOUT=1:
  Docling then skips the ``docling-project/docling-layout-heron`` model and runs
  OCR only, so only the RapidOCR weights above need preloading (no layout model
  download required).
* If ``DOCLING_ARTIFACTS_PATH`` is left unset, Docling falls back to its default
  cache (under ``$HF_HOME``) and auto-downloads on first OCR — but that makes the
  first real Aadhaar pay the download time (the 300s timeout). Prefer the
  explicit pre-fetch above for a warm worker boot.

No real customer document is needed and no data leaves the host.
"""
from __future__ import annotations

import io
import os
import pathlib
import sys

import pymupdf  # PyMuPDF; available wherever Docling OCR runs

from app.knowledge_engine.shared.models import RawSource
from app.infrastructure.providers.parsing.docling_provider import DoclingParsingProvider


def _tiny_image_only_pdf() -> bytes:
    """A 1-page image-only PDF (no selectable text layer) to warm the cache.

    The glyph string is rasterized to a pixmap and stamped as an image, so the
    PyMuPDF fast path yields 0 selectable chars and Docling image OCR runs for
    real (exercising the RapidOCR weights + scale selection) while still
    producing non-empty markdown.
    """
    doc = pymupdf.open()
    page = doc.new_page(width=400, height=200)

    scratch = pymupdf.open()
    scratch_page = scratch.new_page(width=340, height=110)
    scratch_page.insert_text(
        (20, 70), "OCR-CALIBRATION 0123 4567", fontsize=36, color=(0, 0, 0),
    )
    # Rasterize at scale 2.0 (144 DPI) to match the configured OCR raster DPI.
    pixmap = scratch_page.get_pixmap(matrix=pymupdf.Matrix(2.0, 2.0))
    page.insert_image(page.rect, pixmap=pixmap)
    pixmap = None
    scratch.close()

    data = doc.tobytes()
    doc.close()
    return data


def _preflight_cache() -> None:
    """Fail fast with an actionable message instead of a 300s timeout wait.

    The Docling cold-start error (missing ``docling-layout-heron``) is a config
    problem, not a code problem. Surface it here so a botched env is diagnosed
    in milliseconds rather than reproduced as an INGESTION_TIMEOUT_SECONDS abort.
    """
    artifacts_path = os.getenv("DOCLING_ARTIFACTS_PATH", "").strip() or None
    if not artifacts_path:
        print("prewarm: ERROR DOCLING_ARTIFACTS_PATH is unset; set it to the "
              "shared cache dir (e.g. /var/lib/docling/artifacts).")
        sys.exit(2)
    if not os.path.isdir(artifacts_path):
        print(f"prewarm: ERROR artifacts_path={artifacts_path!r} does not exist.")
        sys.exit(2)
    rapidocr_dir = os.path.join(artifacts_path, "RapidOcr")
    weights = sorted(pathlib.Path(rapidocr_dir).glob("PP-OCRv*.onnx"))
    if len(weights) < 3:
        print(f"prewarm: ERROR only {len(weights)} RapidOCR weight(s) found in "
              f"{rapidocr_dir!r}; prefetch with "
              "`docling-tools models download rapidocr "
              "--rapidocr-backend-lang onnxruntime:en -o \"$DOCLING_ARTIFACTS_PATH\"` "
              "and retry.")
        sys.exit(2)
    print(f"preflight: OK artifacts_path={artifacts_path!r} "
          f"rapidocr_weights={len(weights)}")
    skip_layout = os.getenv("DOCLING_SKIP_LAYOUT", "").strip().lower()
    if skip_layout in ("", "0", "false"):
        print("preflight: WARNING DOCLING_SKIP_LAYOUT unset -> Docling will try to "
              "load docling-project/docling-layout-heron, which is NOT in the shared "
              "cache and will reproduce the 300s timeout-to-FileNotFoundError. Set "
              "DOCLING_SKIP_LAYOUT=1 (recommended for scanned/image-only PDFs).")
    else:
        print("preflight: OK layout model skipped (DOCLING_SKIP_LAYOUT=1).")


def main() -> int:
    _preflight_cache()
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
