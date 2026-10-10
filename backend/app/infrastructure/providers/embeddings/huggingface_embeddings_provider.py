from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from math import isfinite

from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError

from app.config.settings import HuggingFaceSettings
from app.core.exceptions import ApplicationError
from app.knowledge_engine.domain.provider_interfaces import EmbeddingProvider

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class HuggingFaceEmbeddingsProvider(EmbeddingProvider):
    settings: HuggingFaceSettings
    vector_dimension: int

    def __post_init__(self) -> None:
        if not self.settings.token:
            raise ApplicationError(
                message=(
                    "HF_TOKEN is required when EMBEDDING_PROVIDER=huggingface. "
                    "Create a Hugging Face token with Inference Providers access."
                ),
                code="huggingface_token_missing",
                status_code=500,
            )
        if self.vector_dimension < 1:
            raise ApplicationError(
                message="Vector store dimension must be positive.",
                code="vector_dimension_invalid",
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

        client = InferenceClient(
            model=self.settings.embedding_model,
            provider=self.settings.inference_provider,
            token=self.settings.token,
            timeout=self.settings.provider_timeout_seconds,
        )
        vectors: list[list[float]] = []
        batch_size = self.settings.embedding_batch_size

        for offset in range(0, len(normalized_texts), batch_size):
            batch = normalized_texts[offset : offset + batch_size]
            started_at = time.monotonic()
            try:
                response = client.feature_extraction(batch)
            except HfHubHTTPError as exc:
                status_code = (
                    exc.response.status_code if exc.response is not None else None
                )
                logger.exception(
                    "Hugging Face embedding request failed",
                    extra={
                        "provider": self.settings.inference_provider,
                        "model": self.settings.embedding_model,
                        "upstream_status": status_code,
                    },
                )
                raise ApplicationError(
                    message=(
                        "Hugging Face embedding request failed"
                        f"{f' with HTTP {status_code}' if status_code else ''}. "
                        "Check the HF token, model/provider availability, and "
                        "Inference Providers billing or credits."
                    ),
                    code="huggingface_embedding_request_failed",
                    status_code=503,
                    details=(
                        {"upstream_status": status_code}
                        if status_code is not None
                        else None
                    ),
                ) from exc

            raw_vectors = response.tolist()
            if (
                isinstance(raw_vectors, list)
                and raw_vectors
                and isinstance(raw_vectors[0], (int, float))
            ):
                raw_vectors = [raw_vectors]
            if not isinstance(raw_vectors, list) or len(raw_vectors) != len(batch):
                raise ApplicationError(
                    message=(
                        "Hugging Face returned a different number of embeddings "
                        "than input texts."
                    ),
                    code="huggingface_embedding_count_mismatch",
                    status_code=502,
                )

            batch_vectors: list[list[float]] = []
            for vector in raw_vectors:
                if not isinstance(vector, list):
                    raise ApplicationError(
                        message="Hugging Face returned an invalid embedding vector.",
                        code="huggingface_embedding_invalid_response",
                        status_code=502,
                    )
                converted_vector = [float(value) for value in vector]
                if len(converted_vector) != self.vector_dimension:
                    raise ApplicationError(
                        message=(
                            "Hugging Face embedding dimensions do not match "
                            f"VECTOR_STORE_DIMENSION={self.vector_dimension}; "
                            f"received {len(converted_vector)}. Configure a "
                            "compatible model or migrate and re-index the vector store."
                        ),
                        code="huggingface_embedding_dimension_mismatch",
                        status_code=502,
                    )
                if not all(isfinite(value) for value in converted_vector):
                    raise ApplicationError(
                        message="Hugging Face returned non-finite embedding values.",
                        code="huggingface_embedding_invalid_values",
                        status_code=502,
                    )
                batch_vectors.append(converted_vector)

            vectors.extend(batch_vectors)
            logger.info(
                "Generated Hugging Face embedding batch",
                extra={
                    "provider": self.settings.inference_provider,
                    "model": self.settings.embedding_model,
                    "batch_size": len(batch),
                    "completed_inputs": len(vectors),
                    "total_inputs": len(normalized_texts),
                    "duration_seconds": round(time.monotonic() - started_at, 3),
                },
            )

        return vectors
