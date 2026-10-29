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

    Docling's StandardPdfPipeline initializes the layout model
    (docling-project/docling-layout-heron) UNCONDITIONALLY on every parse in
    this build -- ``DOCLING_SKIP_LAYOUT=1`` only skips layout *detection*, not
    the model *load*. The heron model must therefore be reachable: present in
    DOCLING_ARTIFACTS_PATH, or auto-downloadable to HF_HOME on first use.
    RapidOCR weights must also be present (in artifacts_path or bundled with
    the rapidocr package). Surface any gap in milliseconds, not as an abort.
    """
    artifacts_path = os.getenv("DOCLING_ARTIFACTS_PATH", "").strip() or None
    hf_home = os.getenv("HF_HOME", "").strip() or None
    heron_dirname = "docling-project--docling-layout-heron"

    # --- RapidOCR weights (3 onnx files) ---
    if artifacts_path:
        weights = sorted(pathlib.Path(artifacts_path, "RapidOcr").glob("PP-OCRv*.onnx"))
    else:
        weights = []
    if len(weights) < 3:
        try:
            import rapidocr  # local import: parsing itself does not need it
            pkg_models = pathlib.Path(rapidocr.__file__).parent / "models"
            weights = sorted(pkg_models.glob("PP-OCRv*.onnx"))
        except Exception:
            weights = []
    if len(weights) < 3:
        print(f"prewarm: ERROR found {len(weights)} RapidOCR onnx weight(s). Prefetch:")
        print("  .venv/bin/docling-tools models download rapidocr "
              "--rapidocr-backend-lang onnxruntime:en -o '$DOCLING_ARTIFACTS_PATH'")
        print("  (or unset DOCLING_ARTIFACTS_PATH so it auto-downloads). Then re-run.")
        sys.exit(2)
    print(f"preflight: OK rapidocr_weights={len(weights)}")

    # --- Layout model (docling-project/docling-layout-heron) ---
    if artifacts_path:
        if pathlib.Path(artifacts_path, heron_dirname).is_dir():
            print(f"preflight: OK layout model present in artifacts_path={artifacts_path!r}")
            return
        print(f"prewarm: ERROR layout model {heron_dirname} not in artifacts_path="
              f"{artifacts_path!r} (Docling always loads it in this version).")
        print("  (a) prefetch: .venv/bin/docling-tools models download-hf-repo "
              "docling-project/docling-layout-heron -o '$DOCLING_ARTIFACTS_PATH'")
        print("  (b) OR unset DOCLING_ARTIFACTS_PATH and let it auto-download to HF_HOME.")
        print("  NOTE: DOCLING_SKIP_LAYOUT=1 only skips layout *detection*, not this load.")
        sys.exit(2)
    # artifacts_path unset -> heron must auto-download into HF_HOME
    if not hf_home:
        print("prewarm: ERROR HF_HOME is unset and artifacts_path has no layout model.")
        print("  Set HF_HOME=<writable dir>, e.g. /var/lib/docling/hf_cache")
        sys.exit(2)
    if not os.path.isdir(hf_home):
        print(f"prewarm: ERROR HF_HOME={hf_home!r} does not exist. Create + chown it:")
        print(f"  sudo mkdir -p {hf_home} && "
              f"sudo chown -R <runtime-user>:<runtime-user> {hf_home}")
        sys.exit(2)
    if not os.access(hf_home, os.W_OK):
        print(f"prewarm: ERROR HF_HOME={hf_home!r} exists but is not writable by this "
              f"user (prior crash was PermissionError writing .../{heron_dirname}).")
        print(f"  sudo chown -R <runtime-user>:<runtime-user> {hf_home}")
        sys.exit(2)
    print(f"preflight: OK layout model will auto-download to HF_HOME={hf_home!r} "
          "(first run only; cached thereafter).")


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
