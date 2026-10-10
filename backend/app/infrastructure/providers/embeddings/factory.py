from __future__ import annotations

from app.config.settings import Settings
from app.core.exceptions import ConfigurationError
from app.infrastructure.providers.embeddings.huggingface_embeddings_provider import (
    HuggingFaceEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.nomic_provider import NomicEmbeddingsProvider
from app.infrastructure.providers.embeddings.openai_embeddings_provider import (
    OpenAIEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.openrouter_embeddings_provider import (
    OpenRouterEmbeddingsProvider,
)
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider


def build_embeddings_provider(settings: Settings) -> EmbeddingProvider:
    provider_name = settings.providers.embeddings.strip().lower()
    if provider_name == "openrouter":
        if (
            settings.openrouter.embedding_dimensions
            != settings.vector_store_dimension
        ):
            raise ConfigurationError(
                "OPENROUTER_EMBEDDING_DIMENSIONS must match "
                "VECTOR_STORE_DIMENSION."
            )
        return OpenRouterEmbeddingsProvider(settings=settings.openrouter)
    if provider_name == "huggingface":
        return HuggingFaceEmbeddingsProvider(
            settings=settings.huggingface,
            vector_dimension=settings.vector_store_dimension,
        )
    if provider_name == "openai":
        return OpenAIEmbeddingsProvider(
            settings=settings.openai_embeddings,
            vector_dimension=settings.vector_store_dimension,
        )
    if provider_name in {"ollama", "nomic"}:
        return NomicEmbeddingsProvider(settings=settings)
    raise ConfigurationError(
        f"Unsupported EMBEDDING_PROVIDER value: {provider_name!r}."
    )
