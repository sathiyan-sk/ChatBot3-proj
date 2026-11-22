from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import ProviderSettings, Settings


@dataclass(frozen=True, slots=True)
class ProviderModelOption:
    provider: str
    model: str | None
    label: str
    embedding_dimensions: int | None = None


@dataclass(frozen=True, slots=True)
class ProviderCatalog:
    parsers: tuple[ProviderModelOption, ...]
    embeddings: tuple[ProviderModelOption, ...]
    llms: tuple[ProviderModelOption, ...]


_PARSER_OPTIONS = (
    ProviderModelOption("docling", None, "Docling"),
    ProviderModelOption("native", None, "Native"),
    ProviderModelOption("auto", None, "Automatic"),
)

_EMBEDDING_OPTIONS = (
    ProviderModelOption(
        "nvidia",
        "nvidia/nv-embedqa-e5-v5",
        "NVIDIA NV-EmbedQA-E5-v5",
        embedding_dimensions=1024,
    ),
    ProviderModelOption(
        "openrouter",
        "qwen/qwen3-embedding-8b",
        "Qwen3 Embedding 8B",
        embedding_dimensions=1024,
    ),
    ProviderModelOption(
        "huggingface",
        "BAAI/bge-large-en-v1.5",
        "BGE Large English v1.5",
        embedding_dimensions=1024,
    ),
    ProviderModelOption(
        "openai",
        "text-embedding-3-small",
        "Text Embedding 3 Small",
        embedding_dimensions=1024,
    ),
    ProviderModelOption(
        "ollama",
        "mxbai-embed-large",
        "MxBai Embed Large",
        embedding_dimensions=1024,
    ),
)

@dataclass(frozen=True, slots=True)
class ActiveProviders:
    llm: str
    embeddings: str
    vector: str
    storage: str


def build_active_providers(settings: ProviderSettings) -> ActiveProviders:
    return ActiveProviders(
        llm=settings.llm,
        embeddings=settings.embeddings,
        vector=settings.vector,
        storage=settings.storage,
    )


def build_provider_catalog(settings: Settings) -> ProviderCatalog:
    enabled_llm_providers = {"ollama"}
    if settings.openai_llm.api_key.strip():
        enabled_llm_providers.add("openai")
    if settings.gemini.api_key.strip():
        enabled_llm_providers.add("gemini")
    if settings.openrouter.api_key.strip():
        enabled_llm_providers.add("openrouter")
    if settings.huggingface.token.strip():
        enabled_llm_providers.add("huggingface")
    if settings.nvidia.api_key.strip():
        enabled_llm_providers.add("nvidia")

    configured_models_by_provider = {
        "ollama": (
            *settings.ollama.llm_models,
            settings.ollama.llm_model_name,
        ),
        "openrouter": (
            *settings.openrouter.models,
            settings.openrouter.model,
        ),
        "openai": (*settings.openai_llm.models, settings.openai_llm.model),
        "gemini": (*settings.gemini.models, settings.gemini.model),
        "huggingface": (
            *settings.huggingface.llm_models,
            settings.huggingface.llm_model,
        ),
        "nvidia": (*settings.nvidia.models, settings.nvidia.model),
    }
    llm_options = []
    seen_llm_options: set[tuple[str, str]] = set()
    for provider, models in configured_models_by_provider.items():
        if provider not in enabled_llm_providers:
            continue
        for model in models:
            normalized_model = model.strip()
            option_key = (provider, normalized_model)
            if normalized_model and option_key not in seen_llm_options:
                llm_options.append(
                    ProviderModelOption(provider, normalized_model, normalized_model)
                )
                seen_llm_options.add(option_key)

    enabled_embedding_providers = {"ollama"}
    if settings.openrouter.api_key.strip():
        enabled_embedding_providers.add("openrouter")
    if settings.huggingface.token.strip():
        enabled_embedding_providers.add("huggingface")
    if settings.openai_embeddings.api_key.strip():
        enabled_embedding_providers.add("openai")
    if settings.nvidia.api_key.strip():
        enabled_embedding_providers.add("nvidia")

    embedding_options = [
        option
        for option in _EMBEDDING_OPTIONS
        if option.provider in enabled_embedding_providers
    ]
    configured_embedding_defaults = (
        (
            "openrouter",
            settings.openrouter.embedding_model,
            settings.openrouter.embedding_dimensions,
        ),
        (
            "openai",
            settings.openai_embeddings.embedding_model,
            settings.openai_embeddings.embedding_dimensions,
        ),
        (
            "nvidia",
            settings.nvidia.embedding_model,
            1024,
        ),
    )
    if (
        settings.openrouter.api_key.strip()
        and settings.openrouter.embedding_dimensions != settings.vector_store_dimension
    ):
        enabled_embedding_providers.discard("openrouter")
        embedding_options = [
            option for option in embedding_options if option.provider != "openrouter"
        ]
    if (
        settings.openai_embeddings.api_key.strip()
        and settings.openai_embeddings.embedding_dimensions
        != settings.vector_store_dimension
    ):
        enabled_embedding_providers.discard("openai")
        embedding_options = [
            option for option in embedding_options if option.provider != "openai"
        ]

    for provider, model, dimensions in configured_embedding_defaults:
        if (
            provider in enabled_embedding_providers
            and dimensions == settings.vector_store_dimension
            and model
            and (
                provider != "nvidia"
                or model == "nvidia/nv-embedqa-e5-v5"
            )
            and not any(
                option.provider == provider and option.model == model
                for option in embedding_options
            )
        ):
            embedding_options.append(
                ProviderModelOption(
                    provider,
                    model,
                    model,
                    embedding_dimensions=dimensions,
                )
            )

    return ProviderCatalog(
        parsers=_PARSER_OPTIONS,
        embeddings=tuple(
            option
            for option in embedding_options
            if option.provider in enabled_embedding_providers
            if option.embedding_dimensions == settings.vector_store_dimension
        ),
        llms=tuple(llm_options),
    )


def is_supported_selection(
    catalog: ProviderCatalog,
    *,
    capability: str,
    provider: str,
    model: str | None,
) -> bool:
    options = {
        "parser": catalog.parsers,
        "embedding": catalog.embeddings,
        "llm": catalog.llms,
    }.get(capability, ())
    return any(
        option.provider == provider and option.model == model
        for option in options
    )


def platform_default_selection(
    settings: Settings,
    *,
    capability: str,
) -> tuple[str, str | None]:
    if capability == "parser":
        return settings.providers.parser, None
    if capability == "llm":
        provider = settings.providers.llm.strip().lower()
        models = {
            "openrouter": settings.openrouter.model,
            "openai": settings.openai_llm.model,
            "gemini": settings.gemini.model,
            "huggingface": settings.huggingface.llm_model,
            "nvidia": settings.nvidia.model,
        }
        model = models.get(provider, settings.ollama.llm_model_name)
        return provider, model
    if capability == "embedding":
        provider = settings.providers.embeddings.strip().lower()
        if provider == "nomic":
            provider = "ollama"
        if provider == "openrouter":
            model = settings.openrouter.embedding_model
        elif provider == "huggingface":
            model = settings.huggingface.embedding_model
        elif provider == "openai":
            model = settings.openai_embeddings.embedding_model
        elif provider == "nvidia":
            model = settings.nvidia.embedding_model
        else:
            model = settings.ollama.embedding_model_name
        return provider, model
    raise ValueError(f"Unsupported provider capability: {capability}.")


def resolve_application_selection(
    settings: Settings,
    application_settings: object | None,
    *,
    capability: str,
) -> tuple[str, str | None]:
    provider, model = platform_default_selection(settings, capability=capability)
    if application_settings is None:
        return provider, model

    fields = {
        "parser": ("parser_provider", None),
        "embedding": ("embedding_provider", "embedding_model"),
        "llm": ("llm_provider", "llm_model"),
    }
    provider_field, model_field = fields[capability]
    configured_provider = getattr(application_settings, provider_field, None)
    configured_model = (
        getattr(application_settings, model_field, None)
        if model_field is not None
        else None
    )
    return configured_provider or provider, configured_model or model