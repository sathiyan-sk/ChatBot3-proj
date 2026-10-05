from types import SimpleNamespace

from app.api.dependencies import get_knowledge_ingestion_pipeline
from app.infrastructure.providers.parsing.docling_provider import DoclingParsingProvider
from app.knowledge_engine.ingestion.parsers.structured_document_parser import (
    StructuredDocumentParser,
)
from app.knowledge_engine.ingestion.parsers.text_parser import TextDocumentParser
from app.knowledge_engine.ingestion.source_loaders.file_loader import FileSourceLoader


def _pipeline_for(source_type: str):
    settings = SimpleNamespace(
        providers=SimpleNamespace(embeddings="nomic"),
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
    pipeline = _pipeline_for("txt")

    assert isinstance(pipeline.source_loader, FileSourceLoader)
    assert isinstance(pipeline.parser, TextDocumentParser)