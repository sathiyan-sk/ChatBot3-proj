from __future__ import annotations

from fastapi import APIRouter, Request, status

router = APIRouter(prefix="/system", tags=["System"])


@router.get(
    "/config",
    status_code=status.HTTP_200_OK,
)
def get_system_config(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    return {
        "status": "ok",
        "app_name": settings.app.app_name,
        "app_version": settings.app.app_version,
        "app_env": settings.app.app_env,
        "provider_llm": settings.providers.llm,
        "provider_embeddings": settings.providers.embeddings,
        "provider_vector": settings.providers.vector,
        "provider_storage": settings.providers.storage,
        "provider_parsing": "pymupdf,python-docx",
        "ollama_chat_model": settings.ollama.llm_model_name,
        "ollama_embed_model": settings.ollama.embedding_model_name,
        "vector_store_table_name": settings.vector_store_table_name,
    }


@router.get(
    "/ingestion-workers",
    status_code=status.HTTP_200_OK,
)
def get_ingestion_worker_status(request: Request) -> dict[str, int | bool]:
    workers = getattr(request.app.state, "ingestion_workers", [])
    return {
        "worker_count": len(workers),
        "running_workers": sum(not worker.done() for worker in workers),
        "healthy": bool(workers) and all(not worker.done() for worker in workers),
    }
