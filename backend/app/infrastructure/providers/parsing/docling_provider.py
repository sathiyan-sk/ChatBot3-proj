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

    def parse(self, source: RawSource) -> ParsedDocument:
        if source.content_bytes is None:
            raise ApplicationError(
                message="Document content is missing.",
                code="document_content_missing",
                status_code=422,
            )

        source_name = source.source_identifier.rsplit("/", 1)[-1] or "document"
        extension = source_name.rsplit(".", 1)[-1].lower()
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
                pdf_pipeline_kwargs: dict = {
                    "artifacts_path": artifacts_path,
                    "layout_options": LayoutObjectDetectionOptions(
                        engine_options=TransformersObjectDetectionEngineOptions(
                            compile_model=False
                        )
                    ),
                }
                if self.do_ocr:
                    ocr_mode_value = {
                        "accurate": OcrMode.ACCURATE,
                        "skip": OcrMode.SKIP,
                        "default": OcrMode.DEFAULT,
                    }.get(self.ocr_mode, OcrMode.DEFAULT)
                    pdf_pipeline_kwargs["do_ocr"] = True
                    pdf_pipeline_kwargs["ocr_options"] = RapidOcrOptions(
                        backend="onnxruntime",
                        lang=[ocr_language],
                        mode=ocr_mode_value,
                    )
                pdf_options = PdfPipelineOptions(
                    **pdf_pipeline_kwargs,
                )
                format_options[InputFormat.PDF] = PdfFormatOption(
                    pipeline_options=pdf_options
                )
            converter_started_at = time.monotonic()
            logger.info(
                "Docling converter initialization started: source_type=%s",
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
    ) -> str:
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
            with pymupdf.open(
                stream=BytesIO(source.content_bytes),
                filetype="pdf",
            ) as pdf:
                for page_number in page_numbers:
                    page = pdf[page_number - 1]
                    pixmap = page.get_pixmap(dpi=self.ocr_image_dpi)
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
