from __future__ import annotations

from dataclasses import replace

from app.config.settings import Settings
from app.core.exceptions import ConfigurationError
from app.infrastructure.providers.embeddings.huggingface_embeddings_provider import (
    HuggingFaceEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.nomic_provider import NomicEmbeddingsProvider
from app.infrastructure.providers.embeddings.nvidia_embeddings_provider import (
    NvidiaEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.openai_embeddings_provider import (
    OpenAIEmbeddingsProvider,
)
from app.infrastructure.providers.embeddings.openrouter_embeddings_provider import (
    OpenRouterEmbeddingsProvider,
)
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider


def build_embeddings_provider(
    settings: Settings,
    *,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> EmbeddingProvider:
    provider_name = (provider_name or settings.providers.embeddings).strip().lower()
    if provider_name == "openrouter":
        provider_settings = replace(
            settings.openrouter,
            embedding_model=model_name or settings.openrouter.embedding_model,
        )
        if provider_settings.embedding_dimensions != settings.vector_store_dimension:
            raise ConfigurationError(
                "OPENROUTER_EMBEDDING_DIMENSIONS must match "
                "VECTOR_STORE_DIMENSION."
            )
        return OpenRouterEmbeddingsProvider(settings=provider_settings)
    if provider_name == "huggingface":
        provider_settings = replace(
            settings.huggingface,
            embedding_model=model_name or settings.huggingface.embedding_model,
        )
        return HuggingFaceEmbeddingsProvider(
            settings=provider_settings,
            vector_dimension=settings.vector_store_dimension,
        )
    if provider_name == "openai":
        provider_settings = replace(
            settings.openai_embeddings,
            embedding_model=model_name or settings.openai_embeddings.embedding_model,
        )
        return OpenAIEmbeddingsProvider(
            settings=provider_settings,
            vector_dimension=settings.vector_store_dimension,
        )
    if provider_name == "nvidia":
        return NvidiaEmbeddingsProvider(
            settings=settings.nvidia,
            model_name=model_name or settings.nvidia.embedding_model,
            vector_dimension=settings.vector_store_dimension,
        )
    if provider_name in {"ollama", "nomic"}:
        ollama_settings = replace(
            settings.ollama,
            embedding_model_name=model_name or settings.ollama.embedding_model_name,
        )
        return NomicEmbeddingsProvider(
            settings=replace(settings, ollama=ollama_settings)
        )
    raise ConfigurationError(
        f"Unsupported EMBEDDING_PROVIDER value: {provider_name!r}."
    )
