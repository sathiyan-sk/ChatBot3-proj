from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.config.settings import Settings
from app.infrastructure.providers.embeddings.nomic_provider import NomicEmbeddingsProvider
from app.infrastructure.providers.embeddings.openrouter_embeddings_provider import (
    OpenRouterEmbeddingsProvider,
)
from app.infrastructure.providers.llm.ollama_provider import OllamaLlmProvider
from app.infrastructure.providers.llm.openrouter_provider import OpenRouterLlmProvider
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.modules.applications.infrastructure.repositories import (
    ApplicationSqlAlchemyRepository,
)
from app.modules.question_answering.application.services import ChatApplicationService
from app.modules.conversations.application.services import ConversationApplicationService
from app.modules.conversations.infrastructure.repositories import (
    SqlAlchemyConversationRepository,
    SqlAlchemyMessageRepository,
)
from app.modules.documents.infrastructure.repositories import SqlAlchemyDocumentRepository
from app.modules.knowledge_bases.infrastructure.repositories import SqlAlchemyKnowledgeBaseRepository
from app.knowledge_engine.pipelines.question_answering_pipeline import QuestionAnsweringPipeline


def _select_llm_provider(settings: Settings):
    if settings.providers.llm.strip().lower() == "openrouter":
        return OpenRouterLlmProvider(
            settings=settings.openrouter,
            fallback_models=settings.openrouter.fallback_models,
        )
    return OllamaLlmProvider(settings=settings.ollama)


def _select_embeddings_provider(settings: Settings):
    if settings.providers.embeddings.strip().lower() == "openrouter":
        return OpenRouterEmbeddingsProvider(settings=settings.openrouter)
    return NomicEmbeddingsProvider(settings=settings)


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    session_factory: sessionmaker
    application_repository: ApplicationSqlAlchemyRepository | None = None
    knowledge_base_repository: SqlAlchemyKnowledgeBaseRepository | None = None
    document_repository: SqlAlchemyDocumentRepository | None = None
    conversation_repository: SqlAlchemyConversationRepository | None = None
    message_repository: SqlAlchemyMessageRepository | None = None
    conversation_application_service: ConversationApplicationService | None = None
    question_answering_pipeline: QuestionAnsweringPipeline | None = None
    chat_application_service: ChatApplicationService | None = None
    llm_provider: object | None = None
    embeddings_provider: object | None = None
    vector_provider: object | None = None


def build_application_container(
    *,
    settings: Settings,
    session_factory: sessionmaker,
) -> ApplicationContainer:
    # Open a temporary session only to build provider objects that need a DB-bound
    # vector store handle. Do not keep a long-lived session on the container.
    temp_session = session_factory()
    try:
        vector_provider = PgVectorProvider(settings=settings, session=temp_session)
    finally:
        temp_session.close()

    return ApplicationContainer(
        settings=settings,
        session_factory=session_factory,
        llm_provider=_select_llm_provider(settings),
        embeddings_provider=_select_embeddings_provider(settings),
        vector_provider=vector_provider,
    )