from __future__ import annotations

import os
import threading
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.config.provider_registry import (
    build_provider_catalog,
    is_supported_selection,
    resolve_application_selection,
)
from app.config.settings import (
    AppSettings,
    DatabaseSettings,
    GeminiSettings,
    HuggingFaceSettings,
    OllamaSettings,
    OpenAIEmbeddingsSettings,
    OpenAILlmSettings,
    OpenRouterSettings,
    NvidiaSettings,
    ProviderSettings,
    Settings,
    StorageSettings,
    load_settings,
)
from app.core.exceptions import ApplicationError
from app.infrastructure.providers.vector.pgvector_provider import PgVectorProvider
from app.knowledge_engine.ingestion.metadata_enricher import MetadataEnricher
from app.knowledge_engine.shared.models import DocumentChunk
from app.modules.settings.application.commands import UpdateSettingsCommand
from app.modules.settings.application.services import SettingsApplicationService
from app.modules.settings.domain.entities import PlatformSettings
from app.modules.settings.infrastructure.repositories import (
    SqlAlchemySettingsRepository,
)
from app.modules.settings.infrastructure.orm_models import SettingsModel


_POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")


def _platform_settings(
    database_url: str,
    *,
    openai_api_key: str = "configured",
) -> Settings:
    return Settings(
        app=AppSettings("test", "0", "test"),
        database=DatabaseSettings(url=database_url),
        providers=ProviderSettings(
            llm="ollama",
            embeddings="ollama",
            vector="pgvector",
            storage="supabase",
            parser="native",
        ),
        storage=StorageSettings("", "", "", 1),
        ollama=OllamaSettings(
            "http://localhost",
            "mxbai-embed-large",
            "qwen2.5:7b",
            1,
            ("qwen2.5:3b", "qwen2.5:7b"),
        ),
        openrouter=OpenRouterSettings(
            "https://example.invalid",
            "",
            "google/gemma-4-26b-a4b-it:free",
            0.2,
            1,
            "qwen/qwen3-embedding-8b",
            1024,
            models=(
                "google/gemma-4-26b-a4b-it:free",
                "google/gemma-4-31b-it:free",
            ),
        ),
        openai_llm=OpenAILlmSettings(
            "https://example.invalid/v1",
            openai_api_key,
            "gpt-4.1-mini",
            0.2,
            1,
            ("gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"),
        ),
        gemini=GeminiSettings(
            "https://example.invalid/v1beta",
            "",
            "gemini-2.5-flash",
            0.2,
            1,
            ("gemini-2.5-flash", "gemini-2.5-pro"),
        ),
        huggingface=HuggingFaceSettings(
            "",
            "BAAI/bge-large-en-v1.5",
            "Qwen/Qwen2.5-7B-Instruct-1M",
            "hf-inference",
            1,
            1,
            ("Qwen/Qwen2.5-7B-Instruct-1M", "google/gemma-2-2b-it"),
            "featherless-ai",
        ),
        nvidia=NvidiaSettings(
            "",
            "https://integrate.api.nvidia.com/v1",
            "nvidia/nemotron-3.5-lightning-30b-a3b",
            1,
            models=(
                "nvidia/nemotron-3.5-lightning-30b-a3b",
                "nvidia/nemotron-3.5-super-120b-a12b",
            ),
        ),
        openai_embeddings=OpenAIEmbeddingsSettings(
            "https://example.invalid/v1",
            openai_api_key,
            "text-embedding-3-small",
            1024,
            1,
            1,
        ),
        vector_store_table_name="document_chunks",
        vector_store_dimension=1024,
    )


def _create_schema(engine) -> None:
    with engine.begin() as connection:
        connection.execute(text("create table applications (id uuid primary key)"))
        connection.execute(
            text(
                """
                create table application_settings (
                    id uuid primary key,
                    application_id uuid not null unique references applications(id),
                    llm_temperature varchar(20) not null,
                    max_context_messages integer not null,
                    inactivity_timeout_minutes integer not null,
                    retention_days integer not null,
                    prompt_system_template text,
                    parser_provider varchar(50),
                    embedding_provider varchar(50),
                    embedding_model varchar(255),
                    llm_provider varchar(50),
                    llm_model varchar(255),
                    created_at timestamptz not null default now(),
                    updated_at timestamptz not null default now()
                )
                """
            )
        )
        connection.execute(
            text(
                """
                create table knowledge_bases (
                    id uuid primary key,
                    application_id uuid not null
                )
                """
            )
        )
        connection.execute(
            text(
                """
                create table documents (
                    id uuid primary key,
                    application_id uuid not null,
                    knowledge_base_id uuid not null,
                    ready_version integer,
                    status varchar(20) not null
                )
                """
            )
        )
        connection.execute(
            text(
                """
                create table document_chunks (
                    chunk_id text not null,
                    document_id text not null,
                    knowledge_base_id text not null,
                    ingestion_version integer not null,
                    metadata_json jsonb,
                    content text not null default '',
                    document_title text not null default '',
                    source_uri text
                )
                """
            )
        )


@pytest.fixture
def postgres_engine():
    if not _POSTGRES_URL:
        pytest.skip("Set TEST_POSTGRES_URL to a dedicated PostgreSQL test database.")

    schema = f"application_settings_test_{uuid4().hex}"
    admin_engine = create_engine(_POSTGRES_URL, poolclass=NullPool)
    with admin_engine.begin() as connection:
        connection.execute(text(f'create schema "{schema}"'))

    engine = create_engine(
        _POSTGRES_URL,
        poolclass=NullPool,
        connect_args={"options": f"-csearch_path={schema}"},
    )
    try:
        _create_schema(engine)
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as connection:
            connection.execute(text(f'drop schema "{schema}" cascade'))
        admin_engine.dispose()


def test_provider_catalog_only_exposes_enabled_models_with_supported_dimensions():
    settings = _platform_settings("", openai_api_key="")
    default_catalog = build_provider_catalog(settings)
    assert {option.provider for option in default_catalog.embeddings} == {"ollama"}
    assert {option.provider for option in default_catalog.llms} == {"ollama"}
    assert all(
        option.embedding_dimensions == settings.vector_store_dimension
        for option in default_catalog.embeddings
    )

    enabled_settings = replace(
        settings,
        openrouter=replace(settings.openrouter, api_key="configured"),
        huggingface=replace(settings.huggingface, token="configured"),
        openai_embeddings=replace(settings.openai_embeddings, api_key="configured"),
    )
    enabled_catalog = build_provider_catalog(enabled_settings)
    assert {option.provider for option in enabled_catalog.embeddings} == {
        "ollama",
        "openrouter",
        "huggingface",
        "openai",
    }
    assert "openrouter" in {option.provider for option in enabled_catalog.llms}
    assert "huggingface" in {option.provider for option in enabled_catalog.llms}
    assert "openai" not in {option.provider for option in enabled_catalog.llms}
    assert "gemini" not in {option.provider for option in enabled_catalog.llms}
    assert "nvidia" not in {option.provider for option in enabled_catalog.llms}
    cloud_llm_settings = replace(
        settings,
        openai_llm=replace(settings.openai_llm, api_key="configured"),
        gemini=replace(settings.gemini, api_key="configured"),
    )
    cloud_llm_catalog = build_provider_catalog(cloud_llm_settings)
    assert {
        option.provider for option in cloud_llm_catalog.llms
    } >= {"openai", "gemini"}
    assert {
        option.model
        for option in cloud_llm_catalog.llms
        if option.provider == "openai"
    } == {"gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"}
    assert {
        option.model
        for option in cloud_llm_catalog.llms
        if option.provider == "gemini"
    } == {"gemini-2.5-flash", "gemini-2.5-pro"}
    configured_model_settings = replace(
        settings,
        ollama=replace(
            settings.ollama,
            llm_models=("qwen2.5:7b", "deployment-approved-ollama-model"),
        ),
        openrouter=replace(
            settings.openrouter,
            api_key="configured",
            models=("google/gemma-4-26b-a4b-it:free", "approved-openrouter-model"),
        ),
        openai_llm=replace(
            settings.openai_llm,
            api_key="configured",
            models=("gpt-4.1-mini", "deployment-approved-model"),
        ),
        gemini=replace(
            settings.gemini,
            api_key="configured",
            models=("gemini-2.5-flash", "deployment-approved-gemini-model"),
        ),
        huggingface=replace(
            settings.huggingface,
            token="configured",
            llm_models=(
                "Qwen/Qwen2.5-7B-Instruct-1M",
                "deployment-approved-huggingface-model",
            ),
        ),
        nvidia=replace(
            settings.nvidia,
            api_key="configured",
            models=(
                "nvidia/nemotron-3.5-lightning-30b-a3b",
                "deployment-approved-nvidia-model",
            ),
        ),
    )
    configured_model_catalog = build_provider_catalog(configured_model_settings)
    assert "deployment-approved-model" in {
        option.model
        for option in configured_model_catalog.llms
        if option.provider == "openai"
    }
    assert "deployment-approved-gemini-model" in {
        option.model
        for option in configured_model_catalog.llms
        if option.provider == "gemini"
    }
    for provider, model in (
        ("ollama", "deployment-approved-ollama-model"),
        ("openrouter", "approved-openrouter-model"),
        ("huggingface", "deployment-approved-huggingface-model"),
        ("nvidia", "deployment-approved-nvidia-model"),
    ):
        assert model in {
            option.model
            for option in configured_model_catalog.llms
            if option.provider == provider
        }
    nvidia_enabled_settings = replace(
        settings,
        nvidia=replace(settings.nvidia, api_key="configured"),
    )
    nvidia_catalog = build_provider_catalog(nvidia_enabled_settings)
    assert {
        option.model for option in nvidia_catalog.llms if option.provider == "nvidia"
    } == {
        "nvidia/nemotron-3.5-lightning-30b-a3b",
        "nvidia/nemotron-3.5-super-120b-a12b",
    }
    assert all(
        option.embedding_dimensions == enabled_settings.vector_store_dimension
        for option in enabled_catalog.embeddings
    )
    incompatible_settings = replace(
        enabled_settings,
        openrouter=replace(enabled_settings.openrouter, embedding_dimensions=768),
        openai_embeddings=replace(
            enabled_settings.openai_embeddings,
            embedding_dimensions=768,
        ),
    )
    incompatible_catalog = build_provider_catalog(incompatible_settings)
    assert "openrouter" not in {
        option.provider for option in incompatible_catalog.embeddings
    }
    assert "openai" not in {
        option.provider for option in incompatible_catalog.embeddings
    }
    assert not is_supported_selection(
        enabled_catalog,
        capability="embedding",
        provider="openai",
        model="unsupported-model",
    )
    assert not is_supported_selection(
        default_catalog,
        capability="llm",
        provider="huggingface",
        model="Qwen/Qwen2.5-7B-Instruct-1M",
    )


def test_llm_catalog_uses_backend_configured_models_for_every_provider(monkeypatch):
    configured_environment = {
        "LLM_MODEL_NAME": "ollama-default",
        "OLLAMA_LLM_MODELS": "ollama-one,ollama-two",
        "OPENROUTER_API_KEY": "configured",
        "OPENROUTER_MODEL": "openrouter-default",
        "OPENROUTER_MODELS": "openrouter-one,openrouter-two",
        "OPENAI_API_KEY": "configured",
        "OPENAI_LLM_MODEL": "openai-default",
        "OPENAI_LLM_MODELS": "openai-one,openai-two",
        "GEMINI_API_KEY": "configured",
        "GEMINI_MODEL": "gemini-default",
        "GEMINI_MODELS": "gemini-one,gemini-two",
        "HF_TOKEN": "configured",
        "HF_LLM_MODEL": "huggingface-default",
        "HF_LLM_MODELS": "huggingface-one,huggingface-two",
        "HF_LLM_INFERENCE_PROVIDER": "featherless-ai",
        "NVIDIA_API_KEY": "configured",
        "NVIDIA_MODEL": "nvidia-default",
        "NVIDIA_MODELS": "nvidia-one,nvidia-two",
    }
    for name, value in configured_environment.items():
        monkeypatch.setenv(name, value)

    catalog = build_provider_catalog(load_settings())
    expected_models = {
        "ollama": {"ollama-one", "ollama-two"},
        "openrouter": {"openrouter-one", "openrouter-two"},
        "openai": {"openai-one", "openai-two"},
        "gemini": {"gemini-one", "gemini-two"},
        "huggingface": {
            "huggingface-one",
            "huggingface-two",
        },
        "nvidia": {"nvidia-one", "nvidia-two"},
    }
    for provider, models in expected_models.items():
        assert {
            option.model for option in catalog.llms if option.provider == provider
        } == models


def test_application_selection_overrides_only_requested_capabilities():
    settings = _platform_settings("")
    application_settings = SimpleNamespace(
        parser_provider="docling",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        llm_provider="ollama",
        llm_model="qwen2.5:3b",
    )
    assert resolve_application_selection(
        settings,
        application_settings,
        capability="parser",
    ) == ("docling", None)
    assert resolve_application_selection(
        settings,
        application_settings,
        capability="embedding",
    ) == ("openai", "text-embedding-3-small")
    assert resolve_application_selection(
        settings,
        application_settings,
        capability="llm",
    ) == ("ollama", "qwen2.5:3b")
    huggingface_settings = SimpleNamespace(
        llm_provider="huggingface",
        llm_model="google/gemma-2-2b-it",
    )
    assert resolve_application_selection(
        settings,
        huggingface_settings,
        capability="llm",
    ) == ("huggingface", "google/gemma-2-2b-it")
    nvidia_settings = SimpleNamespace(
        llm_provider="nvidia",
        llm_model="nvidia/nemotron-3.5-super-120b-a12b",
    )
    assert resolve_application_selection(
        settings,
        nvidia_settings,
        capability="llm",
    ) == ("nvidia", "nvidia/nemotron-3.5-super-120b-a12b")


def test_unconfigured_application_selections_use_platform_defaults():
    settings = _platform_settings("")
    application_settings = SimpleNamespace(
        parser_provider=None,
        embedding_provider=None,
        embedding_model=None,
        llm_provider=None,
        llm_model=None,
    )

    for capability in ("parser", "embedding", "llm"):
        assert resolve_application_selection(
            settings,
            application_settings,
            capability=capability,
        ) == resolve_application_selection(
            settings,
            None,
            capability=capability,
        )


def _create_application(session: Session, settings: Settings) -> str:
    application_id = str(uuid4())
    session.execute(
        text("insert into applications (id) values (cast(:id as uuid))"),
        {"id": application_id},
    )
    repository = SqlAlchemySettingsRepository(session)
    repository.create(
        application_id=application_id,
        llm_temperature="0.2",
        max_context_messages=12,
        inactivity_timeout_minutes=30,
        retention_days=30,
        prompt_system_template=None,
        parser_provider="native",
        embedding_provider="ollama",
        embedding_model="mxbai-embed-large",
        llm_provider="ollama",
        llm_model="qwen2.5:7b",
    )
    return application_id


def _service(session: Session, settings: Settings) -> SettingsApplicationService:
    return SettingsApplicationService(
        settings_repository=SqlAlchemySettingsRepository(session),
        platform_settings=settings,
        provider_catalog=build_provider_catalog(settings),
    )


def _update_command(application_id: str, **selections) -> UpdateSettingsCommand:
    return UpdateSettingsCommand(
        application_id=application_id,
        llm_temperature="0.2",
        max_context_messages=12,
        inactivity_timeout_minutes=30,
        retention_days=30,
        parser_provider=selections.get("parser_provider"),
        embedding_provider=selections.get("embedding_provider"),
        embedding_model=selections.get("embedding_model"),
        llm_provider=selections.get("llm_provider"),
        llm_model=selections.get("llm_model"),
    )


class _MemorySettingsRepository:
    def __init__(self, *, published_vectors: bool = False) -> None:
        now = datetime.now(timezone.utc)
        self.settings = PlatformSettings(
            id=str(uuid4()),
            application_id=str(uuid4()),
            llm_temperature="0.2",
            max_context_messages=12,
            inactivity_timeout_minutes=30,
            retention_days=30,
            prompt_system_template=None,
            parser_provider="native",
            embedding_provider="ollama",
            embedding_model="mxbai-embed-large",
            llm_provider="ollama",
            llm_model="qwen2.5:7b",
            created_at=now,
            updated_at=now,
        )
        self.published_vectors = published_vectors

    def get_by_application_id(self, application_id: str):
        return self.settings

    def get_by_application_id_for_update(self, application_id: str):
        return self.settings

    def has_published_vectors(self, application_id: str) -> bool:
        return self.published_vectors

    def update(self, **values):
        self.settings = replace(
            self.settings,
            **values,
            updated_at=datetime.now(timezone.utc),
        )
        return self.settings


def test_embedding_restriction_only_blocks_actual_embedding_changes():
    settings = _platform_settings("")
    repository = _MemorySettingsRepository(published_vectors=True)
    service = SettingsApplicationService(
        settings_repository=repository,
        platform_settings=settings,
        provider_catalog=build_provider_catalog(settings),
    )
    application_id = repository.settings.application_id

    with pytest.raises(ApplicationError) as error:
        service.update(
            _update_command(
                application_id,
                embedding_provider="openai",
                embedding_model="text-embedding-3-small",
            )
        )
    assert error.value.code == "embedding_change_requires_reembedding"

    parser_result = service.update(
        _update_command(application_id, parser_provider="docling")
    )
    assert parser_result.parser_provider == "docling"
    llm_result = service.update(
        _update_command(application_id, llm_provider="ollama", llm_model="qwen2.5:3b")
    )
    assert llm_result.llm_model == "qwen2.5:3b"
    same_embedding_result = service.update(
        _update_command(
            application_id,
            embedding_provider="ollama",
            embedding_model="mxbai-embed-large",
        )
    )
    assert same_embedding_result.embedding_model == "mxbai-embed-large"


def test_metadata_enricher_records_embedding_provenance():
    chunks = MetadataEnricher(
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimensions=1024,
    ).enrich(
        chunks=[DocumentChunk(chunk_id="chunk-1", content="content")],
        document_id="document-1",
        knowledge_base_id="knowledge-base-1",
        source_type="text",
        source_identifier="source.txt",
        document_title="Source",
        document_metadata={},
        ingestion_version=2,
    )
    assert chunks[0].metadata["embedding_provider"] == "openai"
    assert chunks[0].metadata["embedding_model"] == "text-embedding-3-small"
    assert chunks[0].metadata["embedding_dimensions"] == "1024"


def test_stale_worker_refreshes_settings_and_rolls_back_candidate_vectors(
    postgres_engine,
):
    settings = _platform_settings(_POSTGRES_URL)
    document_id = str(uuid4())
    knowledge_base_id = str(uuid4())

    with Session(postgres_engine) as setup_session:
        application_id = _create_application(setup_session, settings)
        setup_session.execute(
            text(
                """
                insert into documents
                    (id, application_id, knowledge_base_id, ready_version, status)
                values
                    (cast(:id as uuid), cast(:application_id as uuid),
                     cast(:knowledge_base_id as uuid), 7, 'failed')
                """
            ),
            {
                "id": document_id,
                "application_id": application_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        setup_session.commit()

    with Session(postgres_engine) as worker_session:
        stale_identity = worker_session.execute(
            select(SettingsModel).where(
                SettingsModel.application_id == UUID(application_id)
            )
        ).scalar_one()
        captured_selection = (
            stale_identity.embedding_provider,
            stale_identity.embedding_model,
        )

        with Session(postgres_engine) as admin_session:
            result = _service(admin_session, settings).update(
                _update_command(
                    application_id,
                    embedding_provider="openai",
                    embedding_model="text-embedding-3-small",
                )
            )
            assert (result.embedding_provider, result.embedding_model) == (
                "openai",
                "text-embedding-3-small",
            )
            admin_session.commit()

        worker_session.execute(
            text(
                """
                insert into document_chunks
                    (chunk_id, document_id, knowledge_base_id, ingestion_version)
                values (:chunk_id, :document_id, :knowledge_base_id, 8)
                """
            ),
            {
                "chunk_id": "unpublished-candidate",
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        fresh_settings = SqlAlchemySettingsRepository(
            worker_session
        ).get_by_application_id_for_update(application_id)
        assert fresh_settings is not None
        current_selection = resolve_application_selection(
            settings,
            fresh_settings,
            capability="embedding",
        )
        assert current_selection != captured_selection
        try:
            raise ApplicationError(
                message="Captured embedding configuration is stale.",
                code="stale_embedding_configuration",
                status_code=409,
                details={"retryable": True},
            )
        except ApplicationError:
            worker_session.rollback()

    with Session(postgres_engine) as verify_session:
        candidate_count = verify_session.execute(
            text(
                "select count(*) from document_chunks "
                "where chunk_id = 'unpublished-candidate'"
            )
        ).scalar_one()
        ready_version = verify_session.execute(
            text("select ready_version from documents where id = cast(:id as uuid)"),
            {"id": document_id},
        ).scalar_one()
        assert candidate_count == 0
        assert ready_version == 7


def test_stale_reingestion_preserves_previously_published_chunks(postgres_engine):
    settings = _platform_settings(_POSTGRES_URL)
    document_id = str(uuid4())
    knowledge_base_id = str(uuid4())
    with Session(postgres_engine) as setup_session:
        application_id = _create_application(setup_session, settings)
        setup_session.execute(
            text(
                """
                insert into knowledge_bases (id, application_id)
                values (cast(:id as uuid), cast(:application_id as uuid))
                """
            ),
            {"id": knowledge_base_id, "application_id": application_id},
        )
        setup_session.execute(
            text(
                """
                insert into documents
                    (id, application_id, knowledge_base_id, ready_version, status)
                values
                    (cast(:id as uuid), cast(:application_id as uuid),
                     cast(:knowledge_base_id as uuid), 1, 'failed')
                """
            ),
            {
                "id": document_id,
                "application_id": application_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        setup_session.execute(
            text(
                """
                insert into document_chunks
                    (chunk_id, document_id, knowledge_base_id, ingestion_version,
                     content, document_title)
                values
                    ('previously-published', :document_id, :knowledge_base_id, 1,
                     'searchable published content', 'Previous version')
                """
            ),
            {
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        setup_session.commit()

    with Session(postgres_engine) as worker_session:
        stale_identity = worker_session.execute(
            select(SettingsModel).where(
                SettingsModel.application_id == UUID(application_id)
            )
        ).scalar_one()
        captured_selection = (
            stale_identity.embedding_provider,
            stale_identity.embedding_model,
        )
        with Session(postgres_engine) as settings_session:
            settings_session.execute(
                text(
                    """
                    update application_settings
                    set embedding_provider = 'openai',
                        embedding_model = 'text-embedding-3-small'
                    where application_id = cast(:application_id as uuid)
                    """
                ),
                {"application_id": application_id},
            )
            settings_session.commit()

        worker_session.execute(
            text(
                """
                insert into document_chunks
                    (chunk_id, document_id, knowledge_base_id, ingestion_version)
                values ('stale-candidate', :document_id, :knowledge_base_id, 2)
                """
            ),
            {
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        fresh_settings = SqlAlchemySettingsRepository(
            worker_session
        ).get_by_application_id_for_update(application_id)
        assert fresh_settings is not None
        current_selection = resolve_application_selection(
            settings,
            fresh_settings,
            capability="embedding",
        )
        assert current_selection != captured_selection
        worker_session.rollback()

    with Session(postgres_engine) as verify_session:
        chunks = PgVectorProvider(
            settings=SimpleNamespace(vector_store_table_name="document_chunks"),
            session=verify_session,
        ).keyword_search(
            knowledge_base_id=knowledge_base_id,
            query_text="searchable published content",
            top_k=5,
        )
        assert [chunk.chunk_id for chunk in chunks] == ["previously-published"]
        ready_version = verify_session.execute(
            text("select ready_version from documents where id = cast(:id as uuid)"),
            {"id": document_id},
        ).scalar_one()
        assert ready_version == 1


def test_publication_lock_serializes_settings_update_and_published_vectors_block_it(
    postgres_engine,
):
    settings = _platform_settings(_POSTGRES_URL)
    document_id = str(uuid4())
    knowledge_base_id = str(uuid4())
    with Session(postgres_engine) as setup_session:
        application_id = _create_application(setup_session, settings)
        setup_session.execute(
            text(
                """
                insert into documents
                    (id, application_id, knowledge_base_id, ready_version, status)
                values
                    (cast(:id as uuid), cast(:application_id as uuid),
                     cast(:knowledge_base_id as uuid), null, 'processing')
                """
            ),
            {
                "id": document_id,
                "application_id": application_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        setup_session.commit()

    update_started = threading.Event()
    update_finished = threading.Event()
    update_errors: list[ApplicationError] = []

    def update_embedding_selection() -> None:
        update_started.set()
        try:
            with Session(postgres_engine) as admin_session:
                _service(admin_session, settings).update(
                    _update_command(
                        application_id,
                        embedding_provider="openai",
                        embedding_model="text-embedding-3-small",
                    )
                )
                admin_session.commit()
        except ApplicationError as exc:
            update_errors.append(exc)
        finally:
            update_finished.set()

    with Session(postgres_engine) as worker_session:
        repository = SqlAlchemySettingsRepository(worker_session)
        assert repository.get_by_application_id_for_update(application_id)
        update_thread = threading.Thread(target=update_embedding_selection)
        update_thread.start()
        assert update_started.wait(timeout=5)
        assert not update_finished.wait(timeout=0.25)

        worker_session.execute(
            text(
                """
                insert into document_chunks
                    (chunk_id, document_id, knowledge_base_id, ingestion_version)
                values ('published-vector', :document_id, :knowledge_base_id, 1)
                """
            ),
            {
                "document_id": document_id,
                "knowledge_base_id": knowledge_base_id,
            },
        )
        worker_session.execute(
            text("update documents set ready_version = 1 where id = cast(:id as uuid)"),
            {"id": document_id},
        )
        worker_session.commit()
        update_thread.join(timeout=5)

    assert update_finished.is_set()
    assert len(update_errors) == 1
    assert update_errors[0].code == "embedding_change_requires_reembedding"
    with Session(postgres_engine) as verify_session:
        persisted = SqlAlchemySettingsRepository(
            verify_session
        ).get_by_application_id(application_id)
        assert persisted is not None
        assert (persisted.embedding_provider, persisted.embedding_model) == (
            "ollama",
            "mxbai-embed-large",
        )


def test_published_vector_existence_is_scoped_to_the_application(postgres_engine):
    settings = _platform_settings(_POSTGRES_URL)
    first_document_id = str(uuid4())
    first_knowledge_base_id = str(uuid4())
    with Session(postgres_engine) as session:
        first_application_id = _create_application(session, settings)
        second_application_id = _create_application(session, settings)
        session.execute(
            text(
                """
                insert into documents
                    (id, application_id, knowledge_base_id, ready_version, status)
                values
                    (cast(:id as uuid), cast(:application_id as uuid),
                     cast(:knowledge_base_id as uuid), 3, 'pending')
                """
            ),
            {
                "id": first_document_id,
                "application_id": first_application_id,
                "knowledge_base_id": first_knowledge_base_id,
            },
        )
        session.execute(
            text(
                """
                insert into document_chunks
                    (chunk_id, document_id, knowledge_base_id, ingestion_version)
                values ('matching-published-version', :document_id,
                        :knowledge_base_id, 3)
                """
            ),
            {
                "document_id": first_document_id,
                "knowledge_base_id": first_knowledge_base_id,
            },
        )
        session.commit()

    with Session(postgres_engine) as session:
        repository = SqlAlchemySettingsRepository(session)
        assert repository.has_published_vectors(first_application_id)
        assert not repository.has_published_vectors(second_application_id)

    application_b_updated = threading.Event()
    application_b_errors: list[Exception] = []

    def update_application_b() -> None:
        try:
            with Session(postgres_engine) as session:
                result = _service(session, settings).update(
                    _update_command(
                        second_application_id,
                        embedding_provider="openai",
                        embedding_model="text-embedding-3-small",
                    )
                )
                assert result.embedding_provider == "openai"
                session.commit()
        except Exception as exc:
            application_b_errors.append(exc)
        finally:
            application_b_updated.set()

    with Session(postgres_engine) as application_a_lock:
        assert SqlAlchemySettingsRepository(
            application_a_lock
        ).get_by_application_id_for_update(first_application_id)
        update_thread = threading.Thread(target=update_application_b)
        update_thread.start()
        assert application_b_updated.wait(timeout=5)
        application_a_lock.rollback()
        update_thread.join(timeout=5)
    assert not application_b_errors

    with Session(postgres_engine) as session:
        service = _service(session, settings)
        parser_result = service.update(
            _update_command(first_application_id, parser_provider="docling")
        )
        assert parser_result.parser_provider == "docling"
        session.commit()

    with Session(postgres_engine) as session:
        service = _service(session, settings)
        llm_result = service.update(
            _update_command(first_application_id, llm_provider="ollama", llm_model="qwen2.5:3b")
        )
        assert llm_result.llm_model == "qwen2.5:3b"
        same_embedding_result = service.update(
            _update_command(
                first_application_id,
                embedding_provider="ollama",
                embedding_model="mxbai-embed-large",
            )
        )
        assert same_embedding_result.embedding_model == "mxbai-embed-large"
        session.commit()
