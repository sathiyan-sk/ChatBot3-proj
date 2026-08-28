from __future__ import annotations

import os
import secrets
from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.infrastructure.providers.embeddings.nomic_provider import (
    NomicEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.openrouter_embeddings_provider import (
    OpenRouterEmbeddingsProvider,
)
from app.infrastructure.providers.llm.ollama_provider import OllamaLlmProvider
from app.infrastructure.providers.llm.openrouter_provider import (
    OpenRouterLlmProvider,
)
from app.infrastructure.providers.parsing.docling_provider import (
    DoclingParsingProvider,
)
from app.infrastructure.providers.parsing.html_parsing_provider import (
    HtmlParsingProvider,
)
from app.infrastructure.providers.parsing.ocr_provider import OcrParsingProvider
from app.infrastructure.providers.parsing.pymupdf_provider import (
    PyMuPDFParsingProvider,
)
from app.infrastructure.providers.storage.supabase_storage_provider import (
    SupabaseStorageProvider,
)
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.knowledge_engine.generation.citation_builder import CitationBuilder
from app.knowledge_engine.generation.prompt_builder import PromptBuilder
from app.knowledge_engine.generation.response_formatter import ResponseFormatter
from app.knowledge_engine.generation.response_generator import ResponseGenerator
from app.knowledge_engine.ingestion.chunker import IntelligentChunkGenerator
from app.knowledge_engine.ingestion.embedding_generator import EmbeddingGenerator
from app.knowledge_engine.ingestion.metadata_enricher import MetadataEnricher
from app.knowledge_engine.ingestion.normalizer import DocumentNormalizer
from app.knowledge_engine.ingestion.parsers.html_parser import HtmlDocumentParser
from app.knowledge_engine.ingestion.parsers.ocr_parser import OcrDocumentParser
from app.knowledge_engine.ingestion.parsers.text_parser import TextDocumentParser
from app.knowledge_engine.ingestion.parsers.structured_document_parser import (
    StructuredDocumentParser,
)
from app.knowledge_engine.ingestion.source_loaders.csv_loader import CsvSourceLoader
from app.knowledge_engine.ingestion.source_loaders.file_loader import FileSourceLoader
from app.knowledge_engine.ingestion.source_loaders.website_loader import (
    WebsiteSourceLoader,
)
from app.knowledge_engine.ingestion.vector_indexer import VectorIndexer
from app.knowledge_engine.pipelines.knowledge_ingestion_pipeline import (
    KnowledgeIngestionPipeline,
)
from app.knowledge_engine.pipelines.question_answering_pipeline import (
    QuestionAnsweringPipeline,
)
from app.knowledge_engine.retrieval.conversation_context_builder import (
    ConversationContextBuilder,
)
from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.query_embedder import QueryEmbedder
from app.knowledge_engine.retrieval.reranker import Reranker
from app.modules.conversations.application.services import (
    ConversationApplicationService,
)
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.documents.application.services import DocumentApplicationService
from app.modules.documents.infrastructure.repositories import (
    SqlAlchemyDocumentRepository,
)
from app.modules.knowledge_bases.application.services import (
    KnowledgeBaseApplicationService,
)
from app.modules.knowledge_bases.infrastructure.repositories import (
    SqlAlchemyKnowledgeBaseRepository,
)
from app.modules.question_answering.application.services import (
    ChatApplicationService,
)
from app.modules.settings.application.services import SettingsApplicationService
from app.modules.settings.infrastructure.repositories import (
    SqlAlchemySettingsRepository,
)
from app.modules.widgets.application.services import WidgetApplicationService
from app.modules.widgets.infrastructure.repositories import (
    SqlAlchemyWidgetRepository,
)

admin_security = HTTPBasic()


def require_admin(
    request: Request,
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> None:
    settings = request.app.state.settings

    security_settings = getattr(
        settings,
        "security",
        None,
    )

    expected_username = getattr(
        security_settings,
        "admin_username",
        os.getenv("ADMIN_USERNAME", "admin"),
    )

    expected_password = getattr(
        security_settings,
        "admin_password",
        os.getenv("ADMIN_PASSWORD", "change-this-password"),
    )

    username_valid = secrets.compare_digest(
        credentials.username,
        expected_username,
    )

    password_valid = secrets.compare_digest(
        credentials.password,
        expected_password,
    )

    if not username_valid or not password_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials.",
            headers={
                "WWW-Authenticate": "Basic",
            },
        )


def get_container(
    request: Request,
):
    return request.app.state.container


def get_settings(
    request: Request,
) -> Settings:
    return request.app.state.settings


def get_session(
    request: Request,
) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    session: Session = session_factory()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_knowledge_base_application_service(
    session: Session = Depends(get_session),
) -> KnowledgeBaseApplicationService:
    return KnowledgeBaseApplicationService(
        knowledge_base_repository=(
            SqlAlchemyKnowledgeBaseRepository(
                session=session,
            )
        ),
    )


def get_document_application_service(
    request: Request,
    session: Session = Depends(get_session),
) -> DocumentApplicationService:
    app_settings = request.app.state.settings

    return DocumentApplicationService(
        document_repository=(
            SqlAlchemyDocumentRepository(
                session=session,
            )
        ),
        knowledge_base_repository=(
            SqlAlchemyKnowledgeBaseRepository(
                session=session,
            )
        ),
        storage_provider=(
            SupabaseStorageProvider(
                settings=app_settings.storage,
            )
        ),
    )


def get_widget_application_service(
    session: Session = Depends(get_session),
) -> WidgetApplicationService:
    return WidgetApplicationService(
        widget_repository=(
            SqlAlchemyWidgetRepository(
                session=session,
            )
        ),
    )


def get_settings_application_service(
    session: Session = Depends(get_session),
) -> SettingsApplicationService:
    return SettingsApplicationService(
        settings_repository=(
            SqlAlchemySettingsRepository(
                session=session,
            )
        ),
    )


def get_conversation_application_service(
    session: Session = Depends(get_session),
) -> ConversationApplicationService:
    return ConversationApplicationService(
        conversation_repository=(
            SqlAlchemyConversationRepository(
                session=session,
            )
        ),
        message_repository=(
            SqlAlchemyMessageRepository(
                session=session,
            )
        ),
    )


def get_question_answering_pipeline(
    request: Request,
    session: Session = Depends(get_session),
    ) -> QuestionAnsweringPipeline:
    settings = get_settings(request)


    if settings.providers.embeddings.strip().lower() == "openrouter":
        embeddings_provider = OpenRouterEmbeddingsProvider(
            settings=settings.openrouter,
        )
    else:
        embeddings_provider = NomicEmbeddingsProvider(
            settings=settings,
        )


    if settings.providers.llm.strip().lower() == "openrouter":
        llm_provider = OpenRouterLlmProvider(
            settings=settings.openrouter,
            fallback_models=settings.openrouter.fallback_models,
    )
    else:
        llm_provider = OllamaLlmProvider(
            settings=settings.ollama,
    )

    vector_provider = PgVectorProvider(
        settings=settings,
        session=session,
    )

    return QuestionAnsweringPipeline(
        conversation_context_builder=(
            ConversationContextBuilder()
        ),
        query_embedder=(
            QueryEmbedder(
                embeddings_contract=embeddings_provider,
            )
        ),
        hybrid_retriever=(
            HybridRetriever(
                vector_store_contract=vector_provider,
            )
        ),
        metadata_filter=MetadataFilter(),
        reranker=Reranker(),
        prompt_builder=PromptBuilder(),
        response_generator=(
            ResponseGenerator(
                llm_contract=llm_provider,
            )
        ),
        citation_builder=CitationBuilder(),
        response_formatter=ResponseFormatter(),
    )


def get_chat_application_service(
        session: Session = Depends(get_session),
        conversation_service: ConversationApplicationService = Depends(
        get_conversation_application_service,
        ),
        question_answering_pipeline: QuestionAnsweringPipeline = Depends(
        get_question_answering_pipeline,
        ),
        ) -> ChatApplicationService:
    return ChatApplicationService(
        knowledge_base_repository=(
            SqlAlchemyKnowledgeBaseRepository(
                session=session,
            )
        ),
        document_repository=(
            SqlAlchemyDocumentRepository(
                session=session,
            )
        ),
        conversation_service=conversation_service,
        question_answering_pipeline=(
            question_answering_pipeline
        ),
    )


def get_knowledge_ingestion_pipeline(
    source_type: str,
    request: Request,
    session: Session = Depends(get_session),
) -> KnowledgeIngestionPipeline:
    settings = get_settings(request)


    storage_provider = SupabaseStorageProvider(
        settings=settings.storage,
    )


    if settings.providers.embeddings.strip().lower() == "openrouter":
        embeddings_provider = OpenRouterEmbeddingsProvider(
            settings=settings.openrouter,
        )
    else:
        embeddings_provider = NomicEmbeddingsProvider(
            settings=settings,
        )

    vector_provider = PgVectorProvider(
        settings=settings,
        session=session,
    )

    if source_type == "pdf":
        source_loader=FileSourceLoader(
            storage_contract=storage_provider,
        )
        parser=StructuredDocumentParser(
            parsing_contract=PyMuPDFParsingProvider(),
        )

    elif source_type in {"txt", "text", "md", "markdown", "json", "doc", "docx", "xls", "xlsx", "ppt", "pptx"}:
        # Plain-text style formats (and office formats when Docling is
        # unavailable) are decoded directly instead of being forced
        # through the PDF-only Docling converter.
        source_loader = FileSourceLoader(
            storage_contract=storage_provider,
        )

        parser = TextDocumentParser()

    elif source_type == "website":
        source_loader = WebsiteSourceLoader()

        parser = HtmlDocumentParser(
            parsing_contract=HtmlParsingProvider(
                settings=settings,
            )
        )

    elif source_type == "csv":
        source_loader = CsvSourceLoader(
            storage_contract=storage_provider,
        )

        parser = StructuredDocumentParser(
            parsing_contract=DoclingParsingProvider(),
        )

    elif source_type == "image":
        source_loader = FileSourceLoader(
            storage_contract=storage_provider,
        )

        parser = OcrDocumentParser(
            parsing_contract=OcrParsingProvider(
                settings=settings,
            )
        )

    else:
        source_loader = FileSourceLoader(
            storage_contract=storage_provider,
        )

        parser = StructuredDocumentParser(
            parsing_contract=DoclingParsingProvider(),
        )

    return KnowledgeIngestionPipeline(
        source_loader=source_loader,
        parser=parser,
        normalizer=DocumentNormalizer(),
        chunk_generator=IntelligentChunkGenerator(),
        metadata_enricher=MetadataEnricher(),
        embedding_generator=(
            EmbeddingGenerator(
                embeddings_contract=embeddings_provider,
            )
        ),
        vector_indexer=(
            VectorIndexer(
                vector_store_contract=vector_provider,
            )
        ),
    )