from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from math import isfinite

import httpx

from app.config.settings import OpenAIEmbeddingsSettings
from app.core.exceptions import ApplicationError
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenAIEmbeddingsProvider(EmbeddingProvider):
    settings: OpenAIEmbeddingsSettings
    vector_dimension: int

    def __post_init__(self) -> None:
        if not self.settings.api_key:
            raise ApplicationError(
                message=(
                    "OPENAI_API_KEY is required when "
                    "EMBEDDING_PROVIDER=openai."
                ),
                code="openai_embedding_api_key_missing",
                status_code=500,
            )
        if self.settings.embedding_dimensions != self.vector_dimension:
            raise ApplicationError(
                message=(
                    "OPENAI_EMBEDDING_DIMENSIONS must match "
                    f"VECTOR_STORE_DIMENSION ({self.vector_dimension})."
                ),
                code="openai_embedding_dimension_configuration_mismatch",
                status_code=500,
            )

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        normalized_texts = [text.strip() for text in texts]
        if any(not text for text in normalized_texts):
            raise ApplicationError(
                message="Embedding text cannot be empty.",
                code="embedding_text_empty",
                status_code=400,
            )

        vectors: list[list[float]] = []
        for offset in range(0, len(normalized_texts), self.settings.embedding_batch_size):
            batch = normalized_texts[offset : offset + self.settings.embedding_batch_size]
            payload = {
                "model": self.settings.embedding_model,
                "input": batch,
                "dimensions": self.settings.embedding_dimensions,
                "encoding_format": "float",
            }
            started_at = time.monotonic()
            response = self._post_with_retries(payload)
            try:
                response_data = response.json()["data"]
                if not isinstance(response_data, list) or len(response_data) != len(batch):
                    raise ValueError("Embedding count does not match input count.")
                if all(
                    isinstance(item, dict) and isinstance(item.get("index"), int)
                    for item in response_data
                ):
                    response_data = sorted(response_data, key=lambda item: item["index"])
                batch_vectors = [item["embedding"] for item in response_data]
            except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
                raise ApplicationError(
                    message="OpenAI embeddings returned an invalid response.",
                    code="openai_embedding_invalid_response",
                    status_code=502,
                ) from exc

            validated_vectors: list[list[float]] = []
            for vector in batch_vectors:
                if not isinstance(vector, list):
                    raise ApplicationError(
                        message="OpenAI returned an invalid embedding vector.",
                        code="openai_embedding_invalid_response",
                        status_code=502,
                    )
                values = [float(value) for value in vector]
                if len(values) != self.vector_dimension:
                    raise ApplicationError(
                        message=(
                            "OpenAI returned an embedding with "
                            f"{len(values)} dimensions; the vector store expects "
                            f"{self.vector_dimension}."
                        ),
                        code="openai_embedding_dimension_mismatch",
                        status_code=502,
                    )
                if not all(isfinite(value) for value in values):
                    raise ApplicationError(
                        message="OpenAI returned non-finite embedding values.",
                        code="openai_embedding_invalid_values",
                        status_code=502,
                    )
                validated_vectors.append(values)

            vectors.extend(validated_vectors)
            logger.info(
                "Generated OpenAI embedding batch",
                extra={
                    "model": self.settings.embedding_model,
                    "batch_size": len(batch),
                    "completed_inputs": len(vectors),
                    "total_inputs": len(normalized_texts),
                    "duration_seconds": round(time.monotonic() - started_at, 3),
                },
            )
        return vectors

    def _post_with_retries(self, payload: dict[str, object]) -> httpx.Response:
        if not self.settings.base_url:
            raise ApplicationError(
                message="OPENAI_BASE_URL must not be empty.",
                code="openai_embedding_base_url_missing",
                status_code=500,
            )
        url = f"{self.settings.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(1, 4):
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.settings.provider_timeout_seconds,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                status_code = (
                    exc.response.status_code
                    if isinstance(exc, httpx.HTTPStatusError)
                    else None
                )
                retryable = (
                    isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
                    or status_code == 429
                    or (status_code is not None and status_code >= 500)
                )
                if not retryable or attempt == 3:
                    logger.error(
                        "OpenAI embeddings request failed",
                        extra={"attempt": attempt, "upstream_status": status_code},
                    )
                    raise ApplicationError(
                        message=(
                            "OpenAI embeddings request failed"
                            f"{f' with HTTP {status_code}' if status_code else ''}. "
                            "Check the API key, model access, billing, and provider status."
                        ),
                        code="openai_embedding_request_failed",
                        status_code=503,
                        details=(
                            {"upstream_status": status_code}
                            if status_code is not None
                            else None
                        ),
                    ) from exc
                time.sleep(float(attempt))
        raise RuntimeError("OpenAI embeddings retry loop exited unexpectedly.")
