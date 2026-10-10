from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(slots=True, frozen=True)
class AppSettings:
    app_name: str
    app_version: str
    app_env: str


@dataclass(slots=True, frozen=True)
class DatabaseSettings:
    url: str
    database_echo: bool = False
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: float = 30.0
    database_pool_recycle: int = 1800


@dataclass(slots=True, frozen=True)
class StorageSettings:
    supabase_url: str
    supabase_bucket_name: str
    supabase_service_role_key: str
    provider_timeout_seconds: float


@dataclass(slots=True, frozen=True)
class OllamaSettings:
    base_url: str
    embedding_model_name: str
    llm_model_name: str
    provider_timeout_seconds: float

@dataclass(slots=True, frozen=True)
class OpenRouterSettings:
    base_url: str
    api_key: str
    model: str
    temperature: float
    provider_timeout_seconds: float
    embedding_model: str
    embedding_dimensions: int
    fallback_models: tuple[str, ...] = ()
    embedding_batch_size: int = 64


@dataclass(slots=True, frozen=True)
class HuggingFaceSettings:
    token: str
    embedding_model: str
    inference_provider: str
    provider_timeout_seconds: float
    embedding_batch_size: int


@dataclass(slots=True, frozen=True)
class OpenAIEmbeddingsSettings:
    base_url: str
    api_key: str
    embedding_model: str
    embedding_dimensions: int
    provider_timeout_seconds: float
    embedding_batch_size: int


@dataclass(slots=True, frozen=True)
class ProviderSettings:
    llm: str
    embeddings: str
    vector: str
    storage: str


@dataclass(slots=True, frozen=True)
class Settings:
    
    app: AppSettings
    database: DatabaseSettings
    providers: ProviderSettings
    storage: StorageSettings
    ollama: OllamaSettings
    openrouter: OpenRouterSettings
    huggingface: HuggingFaceSettings
    openai_embeddings: OpenAIEmbeddingsSettings

    # These fields are intentionally on the root Settings
    # object because PgVectorProvider expects:
    # settings.vector_store_table_name
    # settings.vector_store_dimension
    vector_store_table_name: str
    vector_store_dimension: int

    provider_timeout_seconds: float = 30.0
    http_user_agent: str = (
        "AI-Knowledge-Platform/1.0"
    )

    # Global CORS origins for first-party surfaces (admin dashboard, web
    # chat). Widget/client origins are resolved PER-APPLICATION from the
    # database (applications.allowed_origins) by DynamicCorsMiddleware.
    cors_allowed_origins: tuple[str, ...] = ()
    cors_allow_local_origins: bool = True
    chat_history_retention_days: int = 30
    ingestion_stale_after_minutes: int = 15
    document_ingestion_concurrency: int = 1
    ingestion_timeout_seconds: int = 300
    langsmith_tracing: bool = False
    langsmith_api_key: str | None = None
    langsmith_project: str | None = None
    langsmith_endpoint: str | None = None

def load_settings() -> Settings:
    langsmith_tracing = os.getenv(
        "LANGSMITH_TRACING",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY", "").strip() or None
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "").strip() or None
    langsmith_endpoint = os.getenv("LANGSMITH_ENDPOINT", "").strip() or None

    if langsmith_tracing and not langsmith_api_key:
        raise ValueError(
            "LANGSMITH_API_KEY is required when LANGSMITH_TRACING is enabled."
        )
    if langsmith_tracing and not langsmith_project:
        raise ValueError(
            "LANGSMITH_PROJECT is required when LANGSMITH_TRACING is enabled."
        )

    provider_timeout_seconds = float(
        os.getenv(
            "PROVIDER_TIMEOUT_SECONDS",
            "30",
        )
    )

    openrouter_timeout_seconds = float(
        os.getenv(
            "OPENROUTER_TIMEOUT_SECONDS",
            str(provider_timeout_seconds),
        )
    )

    ollama_timeout_seconds = float(
        os.getenv(
            "OLLAMA_TIMEOUT_SECONDS",
            str(provider_timeout_seconds),
        )
    )

    return Settings(
        app=AppSettings(
            app_name=os.getenv(
                "APP_NAME",
                "AI Knowledge Platform Backend",
            ),
            app_version=os.getenv(
                "APP_VERSION",
                "0.1.0",
            ),
            app_env=os.getenv(
                "APP_ENV",
                "development",
            ),
        ),
        database=DatabaseSettings(
            url=os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres",
            ),
            database_echo=os.getenv(
                "DATABASE_ECHO",
                "false",
            ).strip().lower()
            in {"1", "true", "yes"},
            database_pool_size=int(
                os.getenv(
                    "DATABASE_POOL_SIZE",
                    "5",
                )
            ),
            database_max_overflow=int(
                os.getenv(
                    "DATABASE_MAX_OVERFLOW",
                    "10",
                )
            ),
            database_pool_timeout=float(
                os.getenv(
                    "DATABASE_POOL_TIMEOUT",
                    "30",
                )
            ),
            database_pool_recycle=int(
                os.getenv(
                    "DATABASE_POOL_RECYCLE",
                    "1800",
                )
            ),
        ),
        providers=ProviderSettings(
            llm=os.getenv(
                "LLM_PROVIDER",
                "ollama",
            ),
            embeddings=os.getenv(
                "EMBEDDING_PROVIDER",
                "ollama",
            ),
            vector=os.getenv(
                "VECTOR_PROVIDER",
                "pgvector",
            ),
            storage=os.getenv(
                "STORAGE_PROVIDER",
                "supabase",
            ),
        ),
        storage=StorageSettings(
            supabase_url=os.getenv(
                "SUPABASE_URL",
                "",
            ),
            supabase_bucket_name=os.getenv(
                "SUPABASE_BUCKET_NAME",
                "data_files",
            ),
            supabase_service_role_key=os.getenv(
                "SUPABASE_SERVICE_ROLE_KEY",
                "",
            ),
            provider_timeout_seconds=provider_timeout_seconds,
        ),
        ollama=OllamaSettings(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://127.0.0.1:11434",
            ),
            embedding_model_name=os.getenv(
                "EMBEDDING_MODEL_NAME",
                "nomic-embed-text",
            ),
            llm_model_name=os.getenv(
                "LLM_MODEL_NAME",
                "qwen2.5:7b",
            ),
            provider_timeout_seconds=ollama_timeout_seconds,
        ),
        openrouter=OpenRouterSettings(
            base_url=os.getenv(
                "OPENROUTER_BASE_URL",
                "https://openrouter.ai/api/v1",
            ),
            api_key=os.getenv(
                "OPENROUTER_API_KEY",
                "",
            ),
            model=os.getenv(
                "OPENROUTER_MODEL",
                "google/gemma-4-26b-a4b-it:free",
            ),
            temperature=float(
                os.getenv(
                    "OPENROUTER_TEMPERATURE",
                    "0.2",
                )
            ),
            provider_timeout_seconds=openrouter_timeout_seconds,
            embedding_model=os.getenv(
                "OPENROUTER_EMBEDDING_MODEL",
                "qwen/qwen3-embedding-8b",
            ),
            embedding_dimensions=int(
                os.getenv(
                    "OPENROUTER_EMBEDDING_DIMENSIONS",
                    "1024",
                )
            ),
            embedding_batch_size=min(
                64,
                max(1, int(os.getenv("OPENROUTER_EMBEDDING_BATCH_SIZE", "64"))),
            ),
            fallback_models=tuple(
                item.strip()
                for item in os.getenv(
                    "OPENROUTER_FALLBACK_MODELS",
                    "",
                ).split(",")
                if item.strip()
            ),
        ),
        huggingface=HuggingFaceSettings(
            token=os.getenv("HF_TOKEN", "").strip(),
            embedding_model=os.getenv(
                "HF_EMBEDDING_MODEL",
                "BAAI/bge-large-en-v1.5",
            ),
            inference_provider=os.getenv(
                "HF_INFERENCE_PROVIDER",
                "hf-inference",
            ),
            provider_timeout_seconds=float(
                os.getenv(
                    "HF_INFERENCE_TIMEOUT_SECONDS",
                    str(provider_timeout_seconds),
                )
            ),
            embedding_batch_size=min(
                64,
                max(1, int(os.getenv("HF_EMBEDDING_BATCH_SIZE", "32"))),
            ),
        ),
        openai_embeddings=OpenAIEmbeddingsSettings(
            base_url=os.getenv(
                "OPENAI_BASE_URL",
                "https://api.openai.com/v1",
            ).rstrip("/"),
            api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            embedding_model=os.getenv(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
            embedding_dimensions=int(
                os.getenv("OPENAI_EMBEDDING_DIMENSIONS", "1024")
            ),
            provider_timeout_seconds=float(
                os.getenv(
                    "OPENAI_EMBEDDING_TIMEOUT_SECONDS",
                    str(provider_timeout_seconds),
                )
            ),
            embedding_batch_size=min(
                64,
                max(1, int(os.getenv("OPENAI_EMBEDDING_BATCH_SIZE", "32"))),
            ),
        ),
        vector_store_table_name=os.getenv(
            "VECTOR_STORE_TABLE_NAME",
            "document_chunks",
        ),
        vector_store_dimension=int(
            os.getenv(
                "VECTOR_STORE_DIMENSION",
                "1024",
            )
        ),
        provider_timeout_seconds=provider_timeout_seconds,
        http_user_agent=os.getenv(
            "HTTP_USER_AGENT",
            "AI-Knowledge-Platform/1.0",
        ),
        cors_allowed_origins=tuple(
            dict.fromkeys(
                item.strip().rstrip("/")
                for item in (
                    os.getenv(
                        "ALLOWED_ORIGINS",
                        "http://localhost:3000,http://localhost:5173",
                    ).split(",")
                    + [os.getenv("FRONTEND_URL", "")]
                )
                if item.strip()
            )
        ),
        cors_allow_local_origins=os.getenv(
            "CORS_ALLOW_LOCAL_ORIGINS",
            "true",
        ).strip().lower()
        in {"1", "true", "yes"},
        chat_history_retention_days=max(
            1,
            int(os.getenv("CHAT_HISTORY_RETENTION_DAYS", "30")),
        ),
        ingestion_stale_after_minutes=max(
            1,
            int(os.getenv("INGESTION_STALE_AFTER_MINUTES", "15")),
        ),
        document_ingestion_concurrency=max(
            1,
            min(8, int(os.getenv("DOCUMENT_INGESTION_CONCURRENCY", "1"))),
        ),
        ingestion_timeout_seconds=max(
            30,
            int(os.getenv("INGESTION_TIMEOUT_SECONDS", "900")),
        ),
        langsmith_tracing=langsmith_tracing,
        langsmith_api_key=langsmith_api_key,
        langsmith_project=langsmith_project,
        langsmith_endpoint=langsmith_endpoint,
    )


def get_settings() -> Settings:
    return load_settings()