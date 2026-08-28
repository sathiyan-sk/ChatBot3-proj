"""One-shot ripple-effect validation for recent refactors.

Run:  python scripts/validate_ripple.py
Exits non-zero on the first failed check.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure the backend root is importable when run as a plain script.
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent),
)


def main() -> None:
    # 1. Single class hierarchy (no duplicate ABCs)
    from app.knowledge_engine.ingestion.source_loader import SourceLoader
    from app.knowledge_engine.ingestion.source_loaders.base import (
        SourceLoader as CanonicalSourceLoader,
    )
    from app.knowledge_engine.ingestion.document_parser import DocumentParser
    from app.knowledge_engine.ingestion.parsers.base import (
        DocumentParser as CanonicalDocumentParser,
    )

    assert SourceLoader is CanonicalSourceLoader, "SourceLoader duplicated!"
    assert DocumentParser is CanonicalDocumentParser, "DocumentParser duplicated!"

    from app.knowledge_engine.ingestion.source_loaders.file_loader import (
        FileSourceLoader,
    )
    from app.knowledge_engine.ingestion.source_loaders.csv_loader import (
        CsvSourceLoader,
    )
    from app.knowledge_engine.ingestion.source_loaders.website_loader import (
        WebsiteSourceLoader,
    )
    from app.knowledge_engine.ingestion.parsers.text_parser import (
        TextDocumentParser,
    )
    from app.knowledge_engine.ingestion.parsers.structured_document_parser import (
        StructuredDocumentParser,
    )
    from app.knowledge_engine.ingestion.parsers.html_parser import (
        HtmlDocumentParser,
    )
    from app.knowledge_engine.ingestion.parsers.ocr_parser import (
        OcrDocumentParser,
    )

    for cls in (FileSourceLoader, CsvSourceLoader, WebsiteSourceLoader):
        assert issubclass(cls, SourceLoader), cls
    for cls in (
        TextDocumentParser,
        StructuredDocumentParser,
        HtmlDocumentParser,
        OcrDocumentParser,
    ):
        assert issubclass(cls, DocumentParser), cls

    # 2. Pipeline accepts the concrete loaders/parsers (type compatibility)
    from app.knowledge_engine.pipelines.knowledge_ingestion_pipeline import (
        KnowledgeIngestionPipeline,
    )
    import inspect

    sig = inspect.signature(KnowledgeIngestionPipeline.__init__)
    loader_hint = sig.parameters["source_loader"].annotation
    parser_hint = sig.parameters["parser"].annotation
    assert issubclass(FileSourceLoader, loader_type(loader_hint)), loader_hint
    assert issubclass(TextDocumentParser, loader_type(parser_hint)), parser_hint

    # 3. Repository satisfies the full interface (incl. delete)
    from app.modules.documents.infrastructure.repositories import (
        SqlAlchemyDocumentRepository,
    )

    for method in (
        "create",
        "get_by_id",
        "list_by_knowledge_base_id",
        "list_by_status",
        "update",
        "delete",
    ):
        assert hasattr(SqlAlchemyDocumentRepository, method), method

    # 4. Engine builds with the extended DatabaseSettings
    from app.config.settings import get_settings
    from app.infrastructure.db.engine import create_database_engine

    engine = create_database_engine(get_settings().database)
    engine.dispose()

    # 5. App imports and routes registered
    from app.main import app  # noqa: F401

    print("ALL_RIPPLE_CHECKS_OK")


def loader_type(annotation):
    """Resolve a possibly-stringified annotation to the actual class."""
    if isinstance(annotation, str):
        module = __import__(
            "app.knowledge_engine.pipelines.knowledge_ingestion_pipeline",
            fromlist=["SourceLoader", "DocumentParser"],
        )
        return getattr(module, annotation.split("|")[0].strip().split("[")[0])
    return annotation


if __name__ == "__main__":
    main()