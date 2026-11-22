from __future__ import annotations

import logging
from math import isfinite
import time

import httpx

from app.config.settings import NvidiaSettings
from app.core.exceptions import ApplicationError, ConfigurationError
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)

_SUPPORTED_MODEL = "nvidia/nv-embedqa-e5-v5"
_SUPPORTED_DIMENSION = 1024


class NvidiaEmbeddingsProvider(EmbeddingProvider):
    def __init__(
        self,
        *,
        settings: NvidiaSettings,
        model_name: str,
        vector_dimension: int,
    ) -> None:
        if not settings.api_key:
            raise ApplicationError(
                message="NVIDIA_API_KEY is required for NVIDIA embeddings.",
                code="nvidia_embedding_api_key_missing",
                status_code=503,
            )
        if model_name != _SUPPORTED_MODEL:
            raise ConfigurationError(
                f"Unsupported NVIDIA embedding model: {model_name!r}."
            )
        if vector_dimension != _SUPPORTED_DIMENSION:
            raise ConfigurationError(
                "NVIDIA NV-EmbedQA-E5-v5 returns 1024 dimensions and requires "
                "VECTOR_STORE_DIMENSION=1024."
            )
        self.settings = settings
        self.model_name = model_name
        self.vector_dimension = vector_dimension

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], input_type="query")[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, input_type="passage")

    def _embed(
        self,
        texts: list[str],
        *,
        input_type: str,
    ) -> list[list[float]]:
        if not texts:
            return []
        normalized_texts = [text.strip() for text in texts]
        if any(not text for text in normalized_texts):
            raise ApplicationError(
                message="Embedding text cannot be empty.",
                code="embedding_text_empty",
                status_code=400,
            )

        base_url = self.settings.base_url.rstrip("/")
        if not base_url:
            raise ConfigurationError("NVIDIA_BASE_URL must not be empty.")

        vectors: list[list[float]] = []
        batch_size = min(64, max(1, self.settings.embedding_batch_size))
        for offset in range(0, len(normalized_texts), batch_size):
            batch = normalized_texts[offset : offset + batch_size]
            started_at = time.monotonic()
            try:
                response = httpx.post(
                    f"{base_url}/embeddings",
                    json={
                        "model": self.model_name,
                        "input": batch,
                        "input_type": input_type,
                        "encoding_format": "float",
                        "truncate": "END",
                    },
                    headers={
                        "Authorization": f"Bearer {self.settings.api_key}",
                        "Content-Type": "application/json",
                    },
                    timeout=self.settings.provider_timeout_seconds,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                retryable = status_code == 429 or status_code >= 500
                raise ApplicationError(
                    message=(
                        "NVIDIA embeddings request failed "
                        f"with HTTP {status_code}. Check API key, model access, "
                        "and NVIDIA API account limits."
                    ),
                    code="nvidia_embedding_request_failed",
                    status_code=503 if retryable else 502,
                    details={
                        "upstream_status": status_code,
                        "retryable": retryable,
                    },
                ) from exc
            except httpx.TimeoutException as exc:
                raise ApplicationError(
                    message="NVIDIA embeddings request timed out.",
                    code="nvidia_embedding_request_failed",
                    status_code=503,
                    details={"retryable": True},
                ) from exc
            except httpx.RequestError as exc:
                raise ApplicationError(
                    message="Could not connect to NVIDIA embeddings.",
                    code="nvidia_embedding_request_failed",
                    status_code=503,
                    details={"retryable": True},
                ) from exc

            try:
                response_data = response.json()["data"]
                if not isinstance(response_data, list) or len(response_data) != len(batch):
                    raise ValueError("Embedding count does not match input count.")
                if all(
                    isinstance(item, dict) and isinstance(item.get("index"), int)
                    for item in response_data
                ):
                    response_data = sorted(
                        response_data,
                        key=lambda item: item["index"],
                    )
                batch_vectors = [item["embedding"] for item in response_data]
            except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
                raise ApplicationError(
                    message="NVIDIA embeddings returned an invalid response.",
                    code="nvidia_embedding_invalid_response",
                    status_code=502,
                ) from exc

            validated_vectors: list[list[float]] = []
            for vector in batch_vectors:
                if not isinstance(vector, list):
                    raise ApplicationError(
                        message="NVIDIA returned an invalid embedding vector.",
                        code="nvidia_embedding_invalid_response",
                        status_code=502,
                    )
                try:
                    values = [float(value) for value in vector]
                except (TypeError, ValueError) as exc:
                    raise ApplicationError(
                        message="NVIDIA returned non-numeric embedding values.",
                        code="nvidia_embedding_invalid_values",
                        status_code=502,
                    ) from exc
                if len(values) != self.vector_dimension:
                    raise ApplicationError(
                        message=(
                            "NVIDIA returned an embedding with "
                            f"{len(values)} dimensions; the vector store expects "
                            f"{self.vector_dimension}."
                        ),
                        code="nvidia_embedding_dimension_mismatch",
                        status_code=502,
                    )
                if not all(isfinite(value) for value in values):
                    raise ApplicationError(
                        message="NVIDIA returned non-finite embedding values.",
                        code="nvidia_embedding_invalid_values",
                        status_code=502,
                    )
                validated_vectors.append(values)

            vectors.extend(validated_vectors)
            logger.info(
                "Generated NVIDIA embedding batch",
                extra={
                    "model": self.model_name,
                    "input_type": input_type,
                    "batch_size": len(batch),
                    "completed_inputs": len(vectors),
                    "total_inputs": len(normalized_texts),
                    "duration_seconds": round(
                        time.monotonic() - started_at,
                        3,
                    ),
                },
            )
        return vectors
