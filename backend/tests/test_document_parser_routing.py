import os
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

from app.api.admin.documents import SUPPORTED_UPLOAD_EXTENSIONS
from app.api.dependencies import get_knowledge_ingestion_pipeline
from app.config.settings import load_settings
from app.infrastructure.providers.parsing.docling_provider import DoclingParsingProvider
from app.infrastructure.providers.parsing.fallback_provider import (
    FallbackParsingProvider,
)
from app.infrastructure.providers.parsing.pymupdf_provider import (
    PyMuPDFParsingProvider,
)
from app.knowledge_engine.ingestion.parsers.csv_parser import CsvDocumentParser
from app.knowledge_engine.ingestion.parsers.structured_document_parser import (
    StructuredDocumentParser,
)
from app.knowledge_engine.ingestion.parsers.text_parser import TextDocumentParser
from app.knowledge_engine.ingestion.source_loaders.file_loader import FileSourceLoader
from app.knowledge_engine.shared.models import RawSource
from app.knowledge_engine.shared.models import ParsedDocument


def _pipeline_for(source_type: str, parsing_provider: str = "pymupdf"):
    settings = SimpleNamespace(
        providers=SimpleNamespace(
            embeddings="nomic",
            parsing=parsing_provider,
        ),
        storage=SimpleNamespace(),
        openrouter=SimpleNamespace(),
        vector_store_table_name="chunks",
        vector_store_dimension=3,
    )
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings))
    )
    return get_knowledge_ingestion_pipeline(
        source_type=source_type,
        request=request,
        session=object(),
    )


def test_docx_uses_structured_parser_instead_of_utf8_text_decoder():
    pipeline = _pipeline_for("docx")

    assert isinstance(pipeline.source_loader, FileSourceLoader)
    assert isinstance(pipeline.parser, StructuredDocumentParser)
    assert isinstance(pipeline.parser.parsing_contract, DoclingParsingProvider)


def test_plain_text_formats_keep_text_parser():
    for source_type in ("txt", "md", "json"):
        pipeline = _pipeline_for(source_type)

        assert isinstance(pipeline.source_loader, FileSourceLoader)
        assert isinstance(pipeline.parser, TextDocumentParser)


def test_csv_keeps_text_source_loader():
    pipeline = _pipeline_for("csv")

    assert pipeline.source_loader.__class__.__name__ == "CsvSourceLoader"
    assert isinstance(pipeline.parser, CsvDocumentParser)


def test_pdf_parser_selector_controls_primary_and_fallback_order():
    docling_pipeline = _pipeline_for("pdf", "docling")
    pymupdf_pipeline = _pipeline_for("pdf", "pymupdf")

    docling_contract = docling_pipeline.parser.parsing_contract
    pymupdf_contract = pymupdf_pipeline.parser.parsing_contract

    assert isinstance(docling_contract, FallbackParsingProvider)
    assert isinstance(docling_contract.primary, DoclingParsingProvider)
    assert isinstance(docling_contract.fallback, PyMuPDFParsingProvider)
    assert isinstance(pymupdf_contract, FallbackParsingProvider)
    assert isinstance(pymupdf_contract.primary, PyMuPDFParsingProvider)
    assert isinstance(pymupdf_contract.fallback, DoclingParsingProvider)


def test_docling_is_the_default_pdf_parser_setting():
    with patch.dict(os.environ):
        os.environ.pop("PARSING_PROVIDER", None)
        assert load_settings().providers.parsing == "docling"


def test_csv_rows_keep_column_names_with_values():
    parsed = CsvDocumentParser().parse(
        RawSource(
            source_type="csv",
            source_identifier="support.csv",
            content_text="plan,price\nBasic,10\nPro,25",
        )
    )

    assert "plan: Basic" in parsed.content
    assert "price: 25" in parsed.content


def test_csv_parser_handles_utf8_bom():
    parsed = CsvDocumentParser().parse(
        RawSource(
            source_type="csv",
            source_identifier="support.csv",
            content_bytes="\ufeffplan,price\nBasic,10".encode("utf-8"),
        )
    )

    assert "plan: Basic" in parsed.content


def test_pdf_parser_falls_back_when_primary_fails():
    parsed_document = ParsedDocument(
        title="guide.pdf",
        content="Fallback text",
        sections=["Fallback text"],
    )

    class FailedParser:
        def parse(self, _source):
            raise RuntimeError("primary parser failed")

    class WorkingParser:
        def parse(self, _source):
            return parsed_document

    result = FallbackParsingProvider(
        primary=FailedParser(),
        fallback=WorkingParser(),
    ).parse(
        RawSource(
            source_type="file",
            source_identifier="guide.pdf",
            content_bytes=b"document bytes",
        )
    )

    assert result == parsed_document


def test_upload_api_supports_the_formats_shown_in_the_registry():
    assert SUPPORTED_UPLOAD_EXTENSIONS == {
        ".pdf",
        ".docx",
        ".txt",
        ".csv",
        ".json",
        ".md",
    }


def test_docling_configures_the_docx_input_format():
    input_format = object()
    captured = {}

    class FakeDocumentStream:
        def __init__(self, *, name, stream):
            self.name = name
            self.stream = stream

    class FakeDocumentConverter:
        def __init__(self, *, allowed_formats):
            captured["allowed_formats"] = allowed_formats

        def convert(self, _document_stream):
            return SimpleNamespace(
                document=SimpleNamespace(
                    export_to_markdown=lambda: "Extracted DOCX text"
                )
            )

    docling_module = ModuleType("docling")
    datamodel_module = ModuleType("docling.datamodel")
    base_models_module = ModuleType("docling.datamodel.base_models")
    base_models_module.DocumentStream = FakeDocumentStream
    base_models_module.InputFormat = SimpleNamespace(
        DOCX=input_format,
        PDF=object(),
    )
    converter_module = ModuleType("docling.document_converter")
    converter_module.DocumentConverter = FakeDocumentConverter

    modules = {
        "docling": docling_module,
        "docling.datamodel": datamodel_module,
        "docling.datamodel.base_models": base_models_module,
        "docling.document_converter": converter_module,
    }

    with patch.dict(sys.modules, modules):
        parsed = DoclingParsingProvider().parse(
            RawSource(
                source_type="file",
                source_identifier="guide.docx",
                content_bytes=b"docx bytes",
            )
        )

    assert captured["allowed_formats"] == [input_format]
    assert parsed.content == "Extracted DOCX text"