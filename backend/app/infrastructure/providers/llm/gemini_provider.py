from __future__ import annotations

from dataclasses import dataclass
import time
from urllib.parse import quote

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class GeminiLlmProvider(LlmProvider):
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
                message="GEMINI_API_KEY is required for Gemini chat inference.",
                code="gemini_api_key_missing",
                status_code=503,
            )

        model = getattr(self.settings, "model", "").strip()
        if not model:
            raise ApplicationError(
                message="Gemini chat model is not configured.",
                code="gemini_llm_model_missing",
                status_code=503,
            )

        base_url = getattr(
            self.settings,
            "base_url",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        if not base_url:
            raise ApplicationError(
                message="GEMINI_BASE_URL must not be empty.",
                code="gemini_base_url_missing",
                status_code=503,
            )

        request_payload: dict[str, object] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": normalized_user}],
                }
            ],
            "generationConfig": {
                "temperature": (
                    temperature
                    if temperature is not None
                    else float(getattr(self.settings, "temperature", 0.2))
                )
            },
        }
        if normalized_system:
            request_payload["systemInstruction"] = {
                "parts": [{"text": normalized_system}]
            }

        timeout = float(
            getattr(self.settings, "provider_timeout_seconds", 30.0)
        )
        started_at = time.perf_counter()
        try:
            response = httpx.post(
                f"{base_url}/models/{quote(model, safe='')}:generateContent",
                json=request_payload,
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code == 429 or status_code >= 500
            raise ApplicationError(
                message=(
                    "Gemini chat request failed "
                    f"with HTTP {status_code} for selected model {model!r}. "
                    "Check the API key, model "
                    "availability, and account billing."
                ),
                code="gemini_llm_request_failed",
                status_code=503 if retryable else 502,
                details={
                    "upstream_status": status_code,
                    "model": model,
                    "retryable": retryable,
                },
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                message="Gemini chat request timed out.",
                code="gemini_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc
        except httpx.RequestError as exc:
            raise ApplicationError(
                message="Could not connect to Gemini chat inference.",
                code="gemini_llm_request_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc

        try:
            payload = response.json()
            candidate = payload["candidates"][0]
            parts = candidate["content"]["parts"]
            generated_text = "".join(
                part["text"]
                for part in parts
                if isinstance(part, dict)
                and isinstance(part.get("text"), str)
                and not part.get("thought", False)
            )
            if not generated_text.strip():
                raise ValueError("response text is empty")
            usage = payload.get("usageMetadata") or {}
            input_tokens = usage.get("promptTokenCount")
            output_tokens = usage.get("candidatesTokenCount")
            total_tokens = usage.get("totalTokenCount")
            input_tokens = int(input_tokens) if input_tokens is not None else None
            output_tokens = int(output_tokens) if output_tokens is not None else None
            total_tokens = int(total_tokens) if total_tokens is not None else None
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ApplicationError(
                message="Gemini returned an invalid chat response.",
                code="gemini_llm_invalid_response",
                status_code=502,
            ) from exc

        return LlmGenerationResult(
            text=generated_text.strip(),
            model=str(payload.get("modelVersion") or model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )