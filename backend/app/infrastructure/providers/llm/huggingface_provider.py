from __future__ import annotations

from dataclasses import dataclass
import time

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class HuggingFaceLlmProvider(LlmProvider):
    settings: object

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> LlmGenerationResult:
        normalized_system = system_prompt.strip()
        normalized_user = user_prompt.strip()
        if not normalized_user:
            raise ApplicationError(
                message="LLM user prompt cannot be empty.",
                code="llm_prompt_empty",
                status_code=400,
            )

        token = getattr(self.settings, "token", "").strip()
        if not token:
            raise ApplicationError(
                message="HF_TOKEN is required for Hugging Face chat inference.",
                code="huggingface_token_missing",
                status_code=503,
            )

        model = getattr(self.settings, "llm_model", "").strip()
        if not model:
            raise ApplicationError(
                message="Hugging Face chat model is not configured.",
                code="huggingface_llm_model_missing",
                status_code=503,
            )

        inference_provider = getattr(
            self.settings,
            "llm_inference_provider",
            "featherless-ai",
        ).strip()
        if not inference_provider:
            raise ApplicationError(
                message=(
                    "HF_LLM_INFERENCE_PROVIDER must name an explicit "
                    "Hugging Face Inference Provider."
                ),
                code="huggingface_llm_provider_missing",
                status_code=503,
            )
        routed_model = (
            model
            if ":" in model
            else f"{model}:{inference_provider}"
        )

        messages: list[dict[str, str]] = []
        if normalized_system:
            messages.append({"role": "system", "content": normalized_system})
        messages.append({"role": "user", "content": normalized_user})

        timeout = float(
            getattr(self.settings, "provider_timeout_seconds", 30.0)
        )
        started_at = time.perf_counter()
        try:
            response = httpx.post(
                "https://router.huggingface.co/v1/chat/completions",
                json={
                    "model": routed_model,
                    "messages": messages,
                    "temperature": (
                        temperature
                        if temperature is not None
                        else float(getattr(self.settings, "llm_temperature", 0.2))
                    ),
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise ApplicationError(
                message=(
                    "Hugging Face chat request failed "
                    f"with HTTP {status_code} for model {model!r} using "
                    f"provider {inference_provider!r}. Check token permissions, "
                    "model/provider availability, and account credits or billing."
                ),
                code="huggingface_llm_request_failed",
                status_code=503 if status_code == 429 or status_code >= 500 else 502,
                details={
                    "upstream_status": status_code,
                    "model": model,
                    "inference_provider": inference_provider,
                    "retryable": status_code == 429 or status_code >= 500,
                },
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                message="Hugging Face chat request timed out.",
                code="huggingface_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc
        except httpx.RequestError as exc:
            raise ApplicationError(
                message="Could not connect to Hugging Face chat inference.",
                code="huggingface_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc

        try:
            payload = response.json()
            generated_text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ApplicationError(
                message="Hugging Face returned an invalid chat response.",
                code="huggingface_llm_invalid_response",
                status_code=502,
            ) from exc
        if not isinstance(generated_text, str) or not generated_text.strip():
            raise ApplicationError(
                message="Hugging Face returned empty chat response text.",
                code="huggingface_llm_invalid_response",
                status_code=502,
            )

        usage = payload.get("usage") or {}
        input_tokens = usage.get("prompt_tokens")
        output_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens")
        if total_tokens is None and (
            input_tokens is not None or output_tokens is not None
        ):
            total_tokens = (input_tokens or 0) + (output_tokens or 0)

        return LlmGenerationResult(
            text=generated_text.strip(),
            model=str(payload.get("model") or model),
            input_tokens=int(input_tokens) if input_tokens is not None else None,
            output_tokens=int(output_tokens) if output_tokens is not None else None,
            total_tokens=int(total_tokens) if total_tokens is not None else None,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )
