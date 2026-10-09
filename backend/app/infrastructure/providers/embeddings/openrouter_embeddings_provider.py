from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OpenRouterEmbeddingsProvider(EmbeddingProvider):
    settings: object

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(
        self,
        texts: list[str],
        *,
        batch_size: int | None = None,
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

        api_key = getattr(self.settings, "api_key", "").strip()
        if not api_key:
            raise ApplicationError(
                message="OpenRouter API key is not configured.",
                code="openrouter_api_key_missing",
                status_code=500,
            )

        base_url = getattr(
            self.settings,
            "base_url",
            "https://openrouter.ai/api/v1",
        ).rstrip("/")

        model = getattr(
            self.settings,
            "embedding_model",
            "qwen/qwen3-embedding-8b",
        )

        dimensions = int(
            getattr(
                self.settings,
                "embedding_dimensions",
                1024,
            )
        )

        timeout = float(
            getattr(
                self.settings,
                "provider_timeout_seconds",
                30.0,
            )
        )

        url = f"{base_url}/embeddings"

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        embeddings: list[list[float]] = []
        configured_batch_size = (
            batch_size
            if batch_size is not None
            else getattr(self.settings, "embedding_batch_size", 64)
        )
        effective_batch_size = min(64, max(1, int(configured_batch_size)))
        for offset in range(0, len(normalized_texts), effective_batch_size):
            batch = normalized_texts[offset : offset + effective_batch_size]
            payload = {
                "model": model,
                "input": batch,
                "dimensions": dimensions,
            }

            batch_started_at = time.monotonic()
            response = self._post_with_retries(
                url=url,
                payload=payload,
                headers=headers,
                timeout=timeout,
            )
            try:
                response_data = response.json()["data"]
                if not isinstance(response_data, list) or len(response_data) != len(batch):
                    raise ValueError("Embedding count does not match input count.")
                if all(
                    isinstance(item, dict)
                    and isinstance(item.get("index"), int)
                    for item in response_data
                ):
                    response_data = sorted(response_data, key=lambda item: item["index"])
                batch_embeddings = [item["embedding"] for item in response_data]
            except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
                raise ApplicationError(
                    message="OpenRouter embeddings returned an invalid response.",
                    code="embedding_provider_invalid_response",
                    status_code=502,
                ) from exc

            if any(
                not isinstance(embedding, list) or not embedding
                for embedding in batch_embeddings
            ):
                raise ApplicationError(
                    message="OpenRouter embeddings returned an empty vector.",
                    code="embedding_provider_empty_response",
                    status_code=502,
                )

            embeddings.extend(batch_embeddings)
            logger.info(
                "Generated OpenRouter embedding batch",
                extra={
                    "batch_size": len(batch),
                    "completed_inputs": len(embeddings),
                    "total_inputs": len(normalized_texts),
                    "duration_seconds": round(
                        time.monotonic() - batch_started_at,
                        3,
                    ),
                },
            )

        return embeddings

    @staticmethod
    def _post_with_retries(
        *,
        url: str,
        payload: dict[str, object],
        headers: dict[str, str],
        timeout: float,
    ) -> httpx.Response:
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                response = httpx.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
                response.raise_for_status()
                return response
            except httpx.HTTPError as exc:
                retryable = (
                    isinstance(exc, (httpx.TimeoutException, httpx.NetworkError))
                    or (
                        isinstance(exc, httpx.HTTPStatusError)
                        and (
                            exc.response.status_code == 429
                            or exc.response.status_code >= 500
                        )
                    )
                )
                if not retryable or attempt == max_attempts:
                    logger.warning(
                        "OpenRouter embeddings request failed after %s attempt(s): %s",
                        attempt,
                        type(exc).__name__,
                    )
                    raise ApplicationError(
                        message=(
                            "OpenRouter embeddings request failed after "
                            f"{attempt} attempt(s): {type(exc).__name__}."
                        ),
                        code="embedding_provider_failed",
                        status_code=502,
                    ) from exc

                delay_seconds = float(attempt)
                logger.warning(
                    "OpenRouter embeddings request hit %s; retrying in %.0f second(s) (%s/%s)",
                    type(exc).__name__,
                    delay_seconds,
                    attempt,
                    max_attempts,
                )
                time.sleep(delay_seconds)

        raise RuntimeError("OpenRouter embeddings retry loop exited unexpectedly.")