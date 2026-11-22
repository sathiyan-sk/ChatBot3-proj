from __future__ import annotations

from dataclasses import dataclass
import time

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class NvidiaLlmProvider(LlmProvider):
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

        api_key = getattr(self.settings, "api_key", "").strip()
        if not api_key:
            raise ApplicationError(
                message="NVIDIA_API_KEY is required for NVIDIA chat inference.",
                code="nvidia_api_key_missing",
                status_code=503,
            )

        model = getattr(self.settings, "model", "").strip()
        if not model:
            raise ApplicationError(
                message="NVIDIA chat model is not configured.",
                code="nvidia_llm_model_missing",
                status_code=503,
            )

        messages: list[dict[str, str]] = []
        if normalized_system:
            messages.append({"role": "system", "content": normalized_system})
        messages.append({"role": "user", "content": normalized_user})

        base_url = getattr(
            self.settings,
            "base_url",
            "https://integrate.api.nvidia.com/v1",
        ).rstrip("/")
        timeout = float(
            getattr(self.settings, "provider_timeout_seconds", 30.0)
        )
        started_at = time.perf_counter()
        try:
            response = httpx.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": (
                        temperature
                        if temperature is not None
                        else float(getattr(self.settings, "temperature", 0.2))
                    ),
                    "stream": False,
                },
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            raise ApplicationError(
                message=(
                    "NVIDIA chat request failed "
                    f"with HTTP {status_code} for selected model {model!r}. "
                    "Check the API key, model "
                    "availability, and NVIDIA API account limits."
                ),
                code="nvidia_llm_request_failed",
                status_code=503 if status_code == 429 or status_code >= 500 else 502,
                details={
                    "upstream_status": status_code,
                    "model": model,
                    "retryable": status_code == 429 or status_code >= 500,
                },
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                message="NVIDIA chat request timed out.",
                code="nvidia_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc
        except httpx.RequestError as exc:
            raise ApplicationError(
                message="Could not connect to NVIDIA chat inference.",
                code="nvidia_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc

        try:
            payload = response.json()
            generated_text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ApplicationError(
                message="NVIDIA returned an invalid chat response.",
                code="nvidia_llm_invalid_response",
                status_code=502,
            ) from exc
        if not isinstance(generated_text, str) or not generated_text.strip():
            raise ApplicationError(
                message="NVIDIA returned empty chat response text.",
                code="nvidia_llm_invalid_response",
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
