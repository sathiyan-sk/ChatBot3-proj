from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

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


@dataclass(slots=True)
class DoclingParsingProvider(ParsingContract):
    def parse(
        self,
        source: RawSource,
    ) -> ParsedDocument:
        if (
            source.content_bytes is None
            and source.content_text is None
        ):
            raise ApplicationError(
                message="Parsing source content is missing.",
                code="parsing_source_missing_content",
                status_code=422,
            )

        if source.content_text is not None:
            extracted_text = source.content_text
        else:
            extracted_text = self._parse_binary_document(
                source,
            )

        normalized_text = normalize_whitespace(
            extracted_text,
        )

        if not normalized_text:
            raise ApplicationError(
                message="Parsed document content is empty.",
                code="docling_parsed_content_empty",
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
            or "document"
        )

        title = (
            source.metadata.get("document_title")
            or source_name
            or "Untitled Document"
        )

        return ParsedDocument(
            title=title,
            content=normalized_text,
            sections=paragraphs or [normalized_text],
            metadata=dict(source.metadata),
        )

    def _parse_binary_document(
        self,
        source: RawSource,
    ) -> str:
        if source.content_bytes is None:
            raise ApplicationError(
                message="Binary document content is missing.",
                code="binary_document_content_missing",
                status_code=422,
            )

        try:
            from docling.datamodel.base_models import (
                DocumentStream,
                InputFormat,
            )
            from docling.document_converter import (
                DocumentConverter,
            )

        except Exception as exc:
            raise ApplicationError(
                message=(
                    "Docling is not available. "
                    "Install Docling and its dependencies."
                ),
                code="docling_dependency_unavailable",
                status_code=503,
            ) from exc

        try:
            source_name = (
                source.source_identifier.rsplit(
                    "/",
                    1,
                )[-1]
                or "document"
            )
            extension = source_name.rsplit(".", 1)[-1].lower()
            input_formats = {
                "pdf": InputFormat.PDF,
                "docx": InputFormat.DOCX,
            }
            input_format = input_formats.get(extension)
            if input_format is None:
                raise ApplicationError(
                    message=(
                        f"Docling does not support the uploaded "
                        f".{extension} format in this configuration."
                    ),
                    code="docling_input_format_unsupported",
                    status_code=415,
                )

            document_stream = DocumentStream(
                name=source_name,
                stream=BytesIO(
                    source.content_bytes,
                ),
            )

            converter = DocumentConverter(
                allowed_formats=[input_format],
            )

            conversion_result = converter.convert(
                document_stream,
            )

            extracted_text = (
                conversion_result.document.export_to_markdown()
            )

            if not extracted_text:
                raise ApplicationError(
                    message=(
                        "Docling returned empty "
                        "document content."
                    ),
                    code="docling_empty_conversion_result",
                    status_code=422,
                )

            return extracted_text

        except ApplicationError:
            raise

        except Exception as exc:
            raise ApplicationError(
                message=(
                    "Docling failed to parse the "
                    f"document: {exc}"
                ),
                code="docling_binary_parsing_failed",
                status_code=422,
            ) from exc