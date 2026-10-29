from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from io import BytesIO

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.parsing import ParsingContract
from app.knowledge_engine.shared.models import (
    DocumentSection,
    ParsedDocument,
    RawSource,
)

logger = logging.getLogger(__name__)
_MARKDOWN_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


@dataclass(slots=True)
class DoclingParsingProvider(ParsingContract):
    max_file_size_bytes: int = 20 * 1024 * 1024
    max_pdf_pages: int = 50
    do_ocr: bool = True
    ocr_mode: str = "default"
    ocr_image_dpi: int = 144

    @staticmethod
    def _resolve_ocr_mode(ocr_mode_enum, requested: str):
        """Resolve a ``DOCLING_OCR_MODE`` string to an ``OcrMode`` member.

        Docling 2.118.0 removed ``OcrMode.ACCURATE`` and never had an
        ``OcrMode.SKIP`` member. The previous implementation dereferenced
        ``OcrMode.ACCURATE`` inside an eagerly-built dict literal, so it raised
        ``AttributeError`` for *every* document (even
        ``DOCLING_OCR_MODE=default``), before the env value was ever consulted.

        Members are therefore resolved by name via ``getattr`` (which returns
        ``None`` instead of raising for absent members) and fall back to
        ``DEFAULT``. Returns ``None`` only if ``DEFAULT`` is itself absent.
        """
        requested = (requested or "default").strip().lower()
        member = getattr(ocr_mode_enum, requested.upper(), None)
        if member is not None:
            return member
        logger.warning(
            "Requested Docling OCR mode %r is unavailable in this docling "
            "version; falling back to DEFAULT. Valid: default, full_page, "
            "layout_regions, pdf_aware_layout_regions. To disable OCR "
            "entirely, use DOCUMENT_PARSER_PROVIDER=native.",
            requested,
        )
        return getattr(ocr_mode_enum, "DEFAULT", None)

    @staticmethod
    def _resolve_ocr_image_scale(
        requested_dpi_env: str | None, default_dpi: int
    ) -> float:
        """Map ``DOCLING_OCR_IMAGE_DPI`` to ``RapidOcrOptions.scale``.

        Docling renders each OCR page at ``72 DPI * scale`` (see docling
        ``OcrOptions.scale``, default ``3.0`` -> 216 DPI). The full Docling path
        previously ignored ``DOCLING_OCR_IMAGE_DPI`` and OCR'd every scanned
        page at 216 DPI, which is the single biggest CPU cost on Aadhaar-style
        card scans. Passing ``scale = dpi / 72`` fixes that and reproduces the
        144 DPI operating point declared in ``.env.example`` (144/72 == 2.0).

        - 144 DPI (scale 2.0) is the default and is the intended point for
          card text; lower it (e.g. 100 -> ~1.39) to cut time on huge scans.
        - Scales below ~72 DPI would downscale below 72 DPI and hurt
          recognition, so the result is clamped at a minimum of 1.0.
        """
        dpi = default_dpi
        if requested_dpi_env:
            requested_dpi_env = requested_dpi_env.strip()
            if requested_dpi_env:
                try:
                    dpi = int(float(requested_dpi_env))
                except ValueError:
                    logger.warning(
                        "Invalid DOCLING_OCR_IMAGE_DPI=%r; using %d.",
                        requested_dpi_env,
                        default_dpi,
                    )
        return max(1.0, dpi / 72.0)

    @staticmethod
    def _resolve_source_extension(source_identifier: str) -> str:
        """Lowercase extension the ``parse`` format allowlist keys off.

        ``parse`` accepts only ``pdf``/``docx`` uploads, so an identifier that
        lacks a trailing ``<name>.<ext>`` collapses to a non-allowlisted
        "extension". This is why the prewarm probe MUST pass a ``.pdf``-suffixed
        identifier (``prewarm:docling-cache.pdf``): the original bare value
        ``prewarm:docling-cache`` has no dot, so ``rsplit`` returns the whole
        string as the "extension" and the parser rejects it with
        ``docling_format_unsupported``.
        """
        source_name = (source_identifier or "").rsplit("/", 1)[-1] or "document"
        return source_name.rsplit(".", 1)[-1].lower()

    def parse(self, source: RawSource) -> ParsedDocument:
        if source.content_bytes is None:
            raise ApplicationError(
                message="Document content is missing.",
                code="document_content_missing",
                status_code=422,
            )

        extension = self._resolve_source_extension(source.source_identifier)
        if extension not in {"pdf", "docx"}:
            raise ApplicationError(
                message=f"Docling parser does not support .{extension} uploads.",
                code="docling_format_unsupported",
                status_code=415,
            )
        if len(source.content_bytes) > self.max_file_size_bytes:
            raise ApplicationError(
                message=(
                    "Document exceeds the configured upload size limit of "
                    f"{self.max_file_size_bytes} bytes."
                ),
                code="document_file_too_large",
                status_code=413,
            )

        if extension == "pdf":
            try:
                import pymupdf

                with pymupdf.open(
                    stream=source.content_bytes,
                    filetype="pdf",
                ) as pdf:
                    page_count = pdf.page_count
            except Exception as exc:
                raise ApplicationError(
                    message="The uploaded PDF could not be opened.",
                    code="pdf_preflight_failed",
                    status_code=422,
                ) from exc
            if page_count > self.max_pdf_pages:
                raise ApplicationError(
                    message=(
                        f"PDF exceeds the configured limit of "
                        f"{self.max_pdf_pages} pages."
                    ),
                    code="pdf_page_limit_exceeded",
                    status_code=413,
                )

        started_at = time.monotonic()
        logger.info(
            "Docling conversion started: source_type=%s bytes=%d",
            extension,
            len(source.content_bytes),
            extra={
                "source_type": extension,
                "source_bytes": len(source.content_bytes),
            },
        )

        try:
            from docling.datamodel.base_models import (
                ConversionStatus,
                InputFormat,
            )
            from docling.datamodel.pipeline_options import (
                OcrMode,
                PdfPipelineOptions,
                RapidOcrOptions,
            )
            from docling.datamodel.pipeline_options import (
                LayoutObjectDetectionOptions,
            )
            from docling.datamodel.object_detection_engine_options import (
                TransformersObjectDetectionEngineOptions,
            )
            from docling.document_converter import (
                DocumentConverter,
                FormatOption,
                PdfFormatOption,
            )
            from docling_core.types.io import DocumentStream
        except ImportError as exc:
            raise ApplicationError(
                message="Docling parser dependencies are unavailable.",
                code="docling_dependency_missing",
                status_code=503,
            ) from exc

        dependencies_loaded_at = time.monotonic()
        logger.info(
            "Docling dependencies loaded: duration_seconds=%.3f",
            dependencies_loaded_at - started_at,
        )

        try:
            input_format = (
                InputFormat.PDF if extension == "pdf" else InputFormat.DOCX
            )
            format_options: dict[InputFormat, FormatOption] = {}
            if input_format == InputFormat.PDF:
                artifacts_path = (
                    os.getenv("DOCLING_ARTIFACTS_PATH", "").strip() or None
                )
                ocr_language = (
                    os.getenv("DOCLING_OCR_LANGUAGE", "en").strip() or "en"
                )
                ocr_mode = (
                    os.getenv("DOCLING_OCR_MODE", self.ocr_mode).strip().lower()
                    or self.ocr_mode
                )
                ocr_scale = self._resolve_ocr_image_scale(
                    os.getenv("DOCLING_OCR_IMAGE_DPI"), self.ocr_image_dpi
                )
                logger.info(
                    "Docling OCR raster scale: DOCLING_OCR_IMAGE_DPI -> "
                    "scale=%.2f (~%d DPI; 72 DPI * scale). "
                    "Lower the DPI env var to cut OCR time on large scans.",
                    ocr_scale,
                    int(round(ocr_scale * 72)),
                )
                pdf_pipeline_kwargs: dict = {
                    "artifacts_path": artifacts_path,
                    "layout_options": LayoutObjectDetectionOptions(
                        engine_options=TransformersObjectDetectionEngineOptions(
                            compile_model=False
                        )
                    ),
                }
                if (
                    os.getenv("DOCLING_SKIP_LAYOUT", "").strip().lower()
                    in {"1", "true", "yes"}
                ):
                    pdf_pipeline_kwargs["do_layout"] = False
                    logger.info(
                        "Docling layout detection disabled "
                        "(DOCLING_SKIP_LAYOUT=1); running OCR without the "
                        "layout model for faster ingestion of scanned images."
                    )
                if self.do_ocr:
                    ocr_mode_value = self._resolve_ocr_mode(OcrMode, ocr_mode)
                    rapid_ocr_kwargs: dict = {
                        "backend": "onnxruntime",
                        "lang": [ocr_language],
                        "scale": ocr_scale,
                    }
                    if ocr_mode_value is not None:
                        rapid_ocr_kwargs["mode"] = ocr_mode_value
                    else:
                        logger.warning(
                            "Docling OcrMode has no usable DEFAULT member; "
                            "relying on RapidOcrOptions built-in default mode."
                        )
                    pdf_pipeline_kwargs["do_ocr"] = True
                    pdf_pipeline_kwargs["ocr_options"] = RapidOcrOptions(
                        **rapid_ocr_kwargs
                    )
                pdf_options = PdfPipelineOptions(
                    **pdf_pipeline_kwargs,
                )
                format_options[InputFormat.PDF] = PdfFormatOption(
                    pipeline_options=pdf_options
                )

            docling_artifacts = os.getenv("DOCLING_ARTIFACTS_PATH", "").strip() or None
            docling_hf_home = os.getenv("HF_HOME", "").strip() or None
            logger.info(
                "Docling initialization preconditions: "
                "artifacts_path=%r hf_home=%r "
                "artifacts_dir_exists=%s hf_cache_dir_exists=%s "
                "(a False/None here means the first ingestion in this "
                "container downloads the layout + OCR models — this is the "
                "dominant init cost, not OCR compute).",
                docling_artifacts,
                docling_hf_home,
                os.path.isdir(docling_artifacts) if docling_artifacts else False,
                os.path.isdir(docling_hf_home) if docling_hf_home else False,
            )
            converter_started_at = time.monotonic()
            logger.info(
                "Docling converter initialization started "
                "(includes model load/download; the cold-cache download is "
                "what makes this step long on a fresh container): source_type=%s",
                extension,
            )
            converter = DocumentConverter(
                allowed_formats=[input_format],
                format_options=format_options,
            )
            conversion_started_at = time.monotonic()
            logger.info(
                "Docling converter initialization completed: duration_seconds=%.3f",
                conversion_started_at - converter_started_at,
            )
            logger.info(
                "Docling document conversion started: source_type=%s bytes=%d",
                extension,
                len(source.content_bytes),
            )
            result = converter.convert(
                DocumentStream(
                    name=source_name,
                    stream=BytesIO(source.content_bytes),
                ),
                raises_on_error=False,
            )
            conversion_completed_at = time.monotonic()
            logger.info(
                "Docling document conversion returned: status=%s duration_seconds=%.3f",
                result.status.value,
                conversion_completed_at - conversion_started_at,
            )
            if result.status != ConversionStatus.SUCCESS:
                raise RuntimeError(
                    f"Docling conversion status was {result.status.value}."
                )
            markdown_started_at = time.monotonic()
            logger.info("Docling Markdown export started")
            markdown = result.document.export_to_markdown().strip()
            logger.info(
                "Docling Markdown export completed: duration_seconds=%.3f characters=%d",
                time.monotonic() - markdown_started_at,
                len(markdown),
            )
        except Exception as exc:
            logger.exception(
                "Docling conversion failed: source_type=%s total_duration_seconds=%.3f",
                extension,
                time.monotonic() - started_at,
                extra={"source_type": extension},
            )
            raise ApplicationError(
                message=f"Docling conversion failed: {exc}",
                code="docling_conversion_failed",
                status_code=422,
            ) from exc

        if not markdown:
            raise ApplicationError(
                message="Docling did not extract any document text.",
                code="docling_content_empty",
                status_code=422,
            )

        structured_sections = self._extract_sections(markdown, source_name)
        document_headings = [
            heading
            for heading in (
                _MARKDOWN_HEADING.match(line)
                for line in markdown.splitlines()
            )
            if heading
        ]
        title = (
            source.metadata.get("document_title")
            or (document_headings[0].group(2) if document_headings else source_name)
        )
        pages = getattr(result.document, "pages", {})
        page_count = len(pages) if pages is not None else 0
        logger.info(
            "Docling conversion completed: source_type=%s duration_seconds=%.3f pages=%d sections=%d markdown_chars=%d",
            extension,
            time.monotonic() - started_at,
            page_count,
            len(structured_sections),
            len(markdown),
            extra={
                "source_type": extension,
                "duration_seconds": round(time.monotonic() - started_at, 3),
                "page_count": page_count,
                "section_count": len(structured_sections),
                "markdown_chars": len(markdown),
            },
        )
        return ParsedDocument(
            title=title,
            content=markdown,
            sections=[section.content for section in structured_sections],
            metadata={
                **source.metadata,
                "parser": "docling",
                "page_count": str(page_count),
            },
            structured_sections=structured_sections,
        )

    def parse_image_pages(
        self,
        source: RawSource,
        page_numbers: list[int],
    ) -> list[str]:
        """Run OCR on ONLY the requested (image-only) pages.

        This is the selective-OCR hook used by the quality-aware orchestrator:
        pages whose text was already recovered by PyMuPDF are never
        reprocessed, so selectable text is preserved and no OCR duplication
        occurs. Each requested page is rasterized and handed to Docling's
        image OCR pipeline individually.
        """
        if not page_numbers:
            return ""

        if source.content_bytes is None:
            raise ApplicationError(
                message="OCR source bytes are required.",
                code="ocr_source_bytes_required",
                status_code=422,
            )

        try:
            import pymupdf
            from docling.datamodel.base_models import (
                ConversionStatus,
                InputFormat,
            )
            from docling.document_converter import DocumentConverter
            from docling_core.types.io import DocumentStream
        except ImportError as exc:
            raise ApplicationError(
                message="Docling image-OCR dependencies are unavailable.",
                code="docling_dependency_missing",
                status_code=503,
            ) from exc

        images: list[tuple[str, bytes]] = []
        try:
            image_dpi = self.ocr_image_dpi
            raw_dpi = os.getenv("DOCLING_OCR_IMAGE_DPI")
            if raw_dpi:
                try:
                    image_dpi = int(raw_dpi)
                except ValueError:
                    logger.warning(
                        "Ignored invalid DOCLING_OCR_IMAGE_DPI=%r; using %d.",
                        raw_dpi,
                        image_dpi,
                    )
            with pymupdf.open(
                stream=BytesIO(source.content_bytes),
                filetype="pdf",
            ) as pdf:
                for page_number in page_numbers:
                    page = pdf[page_number - 1]
                    pixmap = page.get_pixmap(dpi=image_dpi)
                    images.append(
                        (f"page-{page_number}.png", pixmap.tobytes("png"))
                    )
        except Exception as exc:
            raise ApplicationError(
                message=f"Failed to rasterize image-only pages: {exc}",
                code="pdf_rasterization_failed",
                status_code=422,
            ) from exc

        if not images:
            return ""

        converter = DocumentConverter(allowed_formats=[InputFormat.IMAGE])
        extracted: list[str] = []
        for name, png_bytes in images:
            try:
                result = converter.convert(
                    DocumentStream(
                        name=name,
                        stream=BytesIO(png_bytes),
                    ),
                    raises_on_error=False,
                )
            except Exception as exc:
                logger.warning(
                    "Docling image OCR failed for page: %s (%s)",
                    name,
                    exc,
                )
                continue
            if result.status == ConversionStatus.SUCCESS:
                markdown = result.document.export_to_markdown().strip()
                if markdown:
                    extracted.append(markdown)
        return extracted

    @staticmethod
    def _extract_sections(
        markdown: str,
        source_name: str,
    ) -> list[DocumentSection]:
        sections: list[DocumentSection] = []
        heading_stack: list[tuple[int, str]] = []
        current_lines: list[str] = []
        current_level = 1

        def flush() -> None:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append(
                    DocumentSection(
                        heading=" > ".join(heading for _, heading in heading_stack)
                        or source_name,
                        content=content,
                        level=current_level,
                    )
                )
            current_lines.clear()

        for line in markdown.splitlines():
            match = _MARKDOWN_HEADING.match(line)
            if match:
                flush()
                current_level = len(match.group(1))
                heading_stack[:] = [
                    (level, heading)
                    for level, heading in heading_stack
                    if level < current_level
                ]
                heading_stack.append((current_level, match.group(2)))
            else:
                current_lines.append(line)

        flush()
        return sections
