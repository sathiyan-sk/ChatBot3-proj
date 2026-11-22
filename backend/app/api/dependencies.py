from __future__ import annotations

import os
import secrets
from collections.abc import Generator
from dataclasses import replace

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from app.config.settings import Settings
from app.config.provider_registry import (
    build_provider_catalog,
    is_supported_selection,
    resolve_application_selection,
)
from app.core.exceptions import ConfigurationError
from app.infrastructure.observability.tracing import TracedLlmProvider
from app.infrastructure.providers.embeddings.factory import (
    build_embeddings_provider,
)
from app.infrastructure.providers.llm.ollama_provider import OllamaLlmProvider
from app.infrastructure.providers.llm.huggingface_provider import (
    HuggingFaceLlmProvider,
)
from app.infrastructure.providers.llm.gemini_provider import GeminiLlmProvider
from app.infrastructure.providers.llm.nvidia_provider import NvidiaLlmProvider
from app.infrastructure.providers.llm.openai_provider import OpenAILlmProvider
from app.infrastructure.providers.llm.openrouter_provider import (
    OpenRouterLlmProvider,
)
from app.infrastructure.providers.parsing.html_parsing_provider import (
    HtmlParsingProvider,
)
from app.infrastructure.providers.parsing.docling_provider import (
    DoclingParsingProvider,
)
from app.infrastructure.providers.parsing.ocr_provider import OcrParsingProvider
from app.infrastructure.providers.parsing.pymupdf_provider import (
    PyMuPDFParsingProvider,
)
from app.infrastructure.providers.parsing.python_docx_provider import (
    PythonDocxParsingProvider,
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
from app.knowledge_engine.ingestion.parsers.quality_aware_document_parser import (
    QualityAwareDocumentParser,
)
from app.knowledge_engine.ingestion.parsers.csv_parser import CsvDocumentParser
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
from app.knowledge_engine.retrieval.context_builder import ContextBuilder
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
from app.modules.settings.domain.entities import PlatformSettings
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
    credentials: HTTPBasicCredentials = Depends(admin_security),
) -> None:
    expected_username = os.getenv("ADMIN_USERNAME", "").strip()
    expected_password = os.getenv("ADMIN_PASSWORD", "")

    if not expected_username or not expected_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured.",
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


def clear_cors_cache(
    request: Request,
    widget_key: str | None = None,
) -> None:
    """Clear the DynamicCorsMiddleware cache.
    
    Args:
        request: FastAPI Request object
        widget_key: Specific widget key to clear, or None to clear all cache
    """
    if hasattr(request.app.state, "dynamic_cors_middleware"):
        request.app.state.dynamic_cors_middleware.clear_cache(widget_key)
    else:
        # Middleware not initialized or not stored
        pass


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
    return build_document_application_service(
        settings=request.app.state.settings,
        session=session,
    )


def build_document_application_service(
    *,
    settings: Settings,
    session: Session,
) -> DocumentApplicationService:
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
                settings=settings.storage,
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
    request: Request,
    session: Session = Depends(get_session),
) -> SettingsApplicationService:
    settings = get_settings(request)
    return SettingsApplicationService(
        settings_repository=(
            SqlAlchemySettingsRepository(
                session=session,
                vector_store_table_name=settings.vector_store_table_name,
            )
        ),
        platform_settings=settings,
        provider_catalog=build_provider_catalog(settings),
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


def _build_llm_provider(
    settings: Settings,
    *,
    provider_name: str,
    model_name: str | None,
):
    normalized_provider = provider_name.strip().lower()
    model_catalog = build_provider_catalog(settings)
    if not is_supported_selection(
        model_catalog,
        capability="llm",
        provider=normalized_provider,
        model=model_name,
    ):
        raise ConfigurationError(
            "The selected LLM provider/model is not enabled by the platform "
            f"configuration: {normalized_provider!r}/{model_name!r}."
        )
    if normalized_provider == "openrouter":
        llm_settings = replace(
            settings.openrouter,
            model=model_name or settings.openrouter.model,
        )
        return OpenRouterLlmProvider(settings=llm_settings)
    if normalized_provider == "ollama":
        llm_settings = replace(
            settings.ollama,
            llm_model_name=model_name or settings.ollama.llm_model_name,
        )
        return OllamaLlmProvider(settings=llm_settings)
    if normalized_provider == "openai":
        llm_settings = replace(
            settings.openai_llm,
            model=model_name or settings.openai_llm.model,
        )
        return OpenAILlmProvider(settings=llm_settings)
    if normalized_provider == "gemini":
        llm_settings = replace(
            settings.gemini,
            model=model_name or settings.gemini.model,
        )
        return GeminiLlmProvider(settings=llm_settings)
    if normalized_provider == "huggingface":
        llm_settings = replace(
            settings.huggingface,
            llm_model=model_name or settings.huggingface.llm_model,
        )
        return HuggingFaceLlmProvider(settings=llm_settings)
    if normalized_provider == "nvidia":
        llm_settings = replace(
            settings.nvidia,
            model=model_name or settings.nvidia.model,
        )
        return NvidiaLlmProvider(settings=llm_settings)
    raise ConfigurationError(
        f"Unsupported LLM_PROVIDER value: {normalized_provider!r}."
    )


def build_question_answering_pipeline(
    *,
    settings: Settings,
    session: Session,
    application_settings: PlatformSettings | None,
    trace_observer,
) -> QuestionAnsweringPipeline:
    embedding_provider_name, embedding_model_name = resolve_application_selection(
        settings,
        application_settings,
        capability="embedding",
    )
    embeddings_provider = build_embeddings_provider(
        settings,
        provider_name=embedding_provider_name,
        model_name=embedding_model_name,
    )

    llm_provider_name, llm_model_name = resolve_application_selection(
        settings,
        application_settings,
        capability="llm",
    )
    llm_provider = _build_llm_provider(
        settings,
        provider_name=llm_provider_name,
        model_name=llm_model_name,
    )
    traced_llm_provider = TracedLlmProvider(
        provider=llm_provider,
        trace_observer=trace_observer,
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
                expected_dimension=settings.vector_store_dimension,
            )
        ),
        hybrid_retriever=(
            HybridRetriever(
                vector_store_contract=vector_provider,
                rrf_k=settings.retrieval_rrf_k,
            )
        ),
        metadata_filter=MetadataFilter(
            min_score=settings.retrieval_min_score,
        ),
        reranker=Reranker(
            lexical_weight=settings.retrieval_lexical_weight,
        ),
        context_builder=ContextBuilder(
            diversity_lambda=settings.retrieval_diversity_lambda,
            max_chunk_chars=settings.retrieval_max_chunk_chars,
        ),
        prompt_builder=PromptBuilder(),
        response_generator=(
            ResponseGenerator(
                llm_contract=traced_llm_provider,
            )
        ),
        citation_builder=CitationBuilder(),
        response_formatter=ResponseFormatter(),
        trace_observer=trace_observer,
        max_context_tokens=settings.retrieval_max_context_tokens,
        initial_candidate_multiplier=settings.retrieval_initial_multiplier,
        min_initial_candidates=settings.retrieval_min_initial_chunks,
    )


def get_question_answering_pipeline(
    request: Request,
    session: Session = Depends(get_session),
) -> QuestionAnsweringPipeline:
    return build_question_answering_pipeline(
        settings=get_settings(request),
        session=session,
        application_settings=None,
        trace_observer=request.app.state.trace_observer,
    )


def get_chat_application_service(
        request: Request,
        session: Session = Depends(get_session),
        conversation_service: ConversationApplicationService = Depends(
        get_conversation_application_service,
        ),
        ) -> ChatApplicationService:
    settings = get_settings(request)
    trace_observer = request.app.state.trace_observer

    def pipeline_factory(
        application_settings: PlatformSettings | None,
    ) -> QuestionAnsweringPipeline:
        return build_question_answering_pipeline(
            settings=settings,
            session=session,
            application_settings=application_settings,
            trace_observer=trace_observer,
        )

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
        settings_repository=SqlAlchemySettingsRepository(
            session=session,
            vector_store_table_name=settings.vector_store_table_name,
        ),
        conversation_service=conversation_service,
        question_answering_pipeline_factory=pipeline_factory,
    )


def get_knowledge_ingestion_pipeline(
    source_type: str,
    request: Request,
    session: Session = Depends(get_session),
) -> KnowledgeIngestionPipeline:
    return build_knowledge_ingestion_pipeline(
        source_type=source_type,
        settings=get_settings(request),
        session=session,
    )


def build_knowledge_ingestion_pipeline(
    *,
    source_type: str,
    settings: Settings,
    session: Session,
    application_settings: PlatformSettings | None = None,
) -> KnowledgeIngestionPipeline:

    storage_provider = SupabaseStorageProvider(
        settings=settings.storage,
    )


    embedding_provider_name, embedding_model_name = resolve_application_selection(
        settings,
        application_settings,
        capability="embedding",
    )
    embeddings_provider = build_embeddings_provider(
        settings,
        provider_name=embedding_provider_name,
        model_name=embedding_model_name,
    )

    vector_provider = PgVectorProvider(
        settings=settings,
        session=session,
    )

    if source_type in {"pdf", "docx"}:
        source_loader = FileSourceLoader(
            storage_contract=storage_provider,
        )
        parser_provider = resolve_application_selection(
            settings,
            application_settings,
            capability="parser",
        )[0].strip().lower()
        if parser_provider == "auto":
            if source_type == "pdf":
                parser = QualityAwareDocumentParser(
                    fast_parser=PyMuPDFParsingProvider(),
                    ocr_parser=DoclingParsingProvider(
                        max_file_size_bytes=getattr(
                            settings,
                            "max_upload_file_size_bytes",
                            20 * 1024 * 1024,
                        ),
                        max_pdf_pages=getattr(settings, "max_pdf_pages", 50),
                        do_ocr=True,
                    ),
                    selectable_ratio_threshold=getattr(
                        settings, "selectable_text_ratio_threshold", 0.5
                    ),
                )
            else:
                parser = StructuredDocumentParser(
                    parsing_contract=DoclingParsingProvider(
                        max_file_size_bytes=getattr(
                            settings,
                            "max_upload_file_size_bytes",
                            20 * 1024 * 1024,
                        ),
                        max_pdf_pages=getattr(settings, "max_pdf_pages", 50),
                        do_ocr=False,
                    ),
                )
        elif parser_provider == "docling":
            parser = StructuredDocumentParser(
                parsing_contract=DoclingParsingProvider(
                    max_file_size_bytes=getattr(
                        settings,
                        "max_upload_file_size_bytes",
                        20 * 1024 * 1024,
                    ),
                    max_pdf_pages=getattr(settings, "max_pdf_pages", 50),
                ),
            )
        elif parser_provider == "native" and source_type == "pdf":
            parser = StructuredDocumentParser(
                parsing_contract=PyMuPDFParsingProvider(),
            )
        elif parser_provider == "native":
            parser = StructuredDocumentParser(
                parsing_contract=PythonDocxParsingProvider(),
            )
        else:
            raise ValueError(
                "Unsupported DOCUMENT_PARSER_PROVIDER "
                f"{settings.providers.parser!r}; choose 'docling', "
                "'native' or 'auto'."
            )

    elif source_type in {"txt", "text", "md", "markdown", "json"}:
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

        parser = CsvDocumentParser()

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
        raise ValueError(
            f"Unsupported ingestion source type: {source_type}."
        )

    return KnowledgeIngestionPipeline(
        source_loader=source_loader,
        parser=parser,
        normalizer=DocumentNormalizer(),
        chunk_generator=IntelligentChunkGenerator(),
        metadata_enricher=MetadataEnricher(
            embedding_provider=embedding_provider_name,
            embedding_model=embedding_model_name,
            embedding_dimensions=settings.vector_store_dimension,
        ),
        embedding_generator=(
            EmbeddingGenerator(
                embeddings_contract=embeddings_provider,
                expected_dimension=settings.vector_store_dimension,
            )
        ),
        vector_indexer=(
            VectorIndexer(
                vector_store_contract=vector_provider,
            )
        ),
    )