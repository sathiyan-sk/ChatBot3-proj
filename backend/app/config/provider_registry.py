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

_LLM_OPTIONS = (
    ProviderModelOption("openrouter", "google/gemma-4-26b-a4b-it:free", "Gemma 4 26B"),
    ProviderModelOption("openrouter", "qwen/qwen-2.5-7b-instruct", "Qwen 2.5 7B Instruct"),
    ProviderModelOption("ollama", "qwen2.5:3b", "Qwen 2.5 3B"),
    ProviderModelOption("ollama", "qwen2.5:7b", "Qwen 2.5 7B"),
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
    if settings.openrouter.api_key.strip():
        enabled_llm_providers.add("openrouter")

    llm_options = [
        option for option in _LLM_OPTIONS if option.provider in enabled_llm_providers
    ]
    configured_llm_models = []
    llm_provider = settings.providers.llm.strip().lower()
    if llm_provider == "openrouter" and "openrouter" in enabled_llm_providers:
        configured_llm_models = [
            settings.openrouter.model,
            *settings.openrouter.fallback_models,
        ]
    elif llm_provider == "ollama":
        configured_llm_models = [settings.ollama.llm_model_name]
    for model in configured_llm_models:
        if model and not any(
            option.provider == llm_provider and option.model == model
            for option in llm_options
        ):
            llm_options.append(
                ProviderModelOption(llm_provider, model, model)
            )

    enabled_embedding_providers = {"ollama"}
    if settings.openrouter.api_key.strip():
        enabled_embedding_providers.add("openrouter")
    if settings.huggingface.token.strip():
        enabled_embedding_providers.add("huggingface")
    if settings.openai_embeddings.api_key.strip():
        enabled_embedding_providers.add("openai")

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
        model = (
            settings.openrouter.model
            if provider == "openrouter"
            else settings.ollama.llm_model_name
        )
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