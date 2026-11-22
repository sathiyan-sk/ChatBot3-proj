from __future__ import annotations

from dataclasses import dataclass
import time

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class OpenRouterLlmProvider(LlmProvider):
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
                message="OpenRouter API key is not configured.",
                code="openrouter_api_key_missing",
                status_code=500,
            )

        base_url = getattr(
            self.settings,
            "base_url",
            "https://openrouter.ai/api/v1",
        ).rstrip("/")

        model = getattr(self.settings, "model", "").strip()
        if not model:
            raise ApplicationError(
                message="OpenRouter model is not configured.",
                code="openrouter_model_missing",
                status_code=500,
            )

        effective_temperature = (
            temperature
            if temperature is not None
            else float(getattr(self.settings, "temperature", 0.2))
        )

        messages: list[dict[str, str]] = []
        if normalized_system:
            messages.append({"role": "system", "content": normalized_system})
        messages.append({"role": "user", "content": normalized_user})

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8000",
            "X-Title": "AI Knowledge Platform",
        }

        timeout = float(
            getattr(
                self.settings,
                "provider_timeout_seconds",
                30.0,
            )
        )

        started_at = time.perf_counter()
        try:
            response = httpx.post(
                f"{base_url}/chat/completions",
                json={
                    "model": model,
                    "messages": messages,
                    "temperature": effective_temperature,
                    "stream": False,
                },
                headers=headers,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            retryable = status_code == 429 or status_code >= 500
            upstream_message = None
            upstream_provider = None
            upstream_detail = None
            try:
                error_payload = exc.response.json()
            except ValueError:
                error_payload = None
            if isinstance(error_payload, dict):
                provider_error = error_payload.get("error")
                if isinstance(provider_error, dict):
                    message = provider_error.get("message")
                    if isinstance(message, str) and message.strip():
                        upstream_message = message.strip()[:300]
                    metadata = provider_error.get("metadata")
                    if isinstance(metadata, dict):
                        provider_name = metadata.get("provider_name")
                        if isinstance(provider_name, str) and provider_name.strip():
                            upstream_provider = provider_name.strip()[:100]
                        raw_detail = metadata.get("raw")
                        if isinstance(raw_detail, str) and raw_detail.strip():
                            upstream_detail = raw_detail.strip()[:300]
            retry_after = exc.response.headers.get("Retry-After")
            if retry_after:
                retry_after = retry_after.strip()[:100]
            if status_code == 429:
                failure_message = (
                    "OpenRouter rate-limited the request "
                    f"for selected model {model!r} (HTTP 429). "
                    "Check provider/account limits or retry later."
                )
            else:
                failure_message = (
                    "OpenRouter chat request failed "
                    f"with HTTP {status_code} for selected model {model!r}."
                )
            if upstream_provider:
                failure_message += f" Upstream provider: {upstream_provider}."
            if upstream_message and upstream_message.lower() != "provider returned error":
                failure_message += f" OpenRouter reported: {upstream_message}"
            if upstream_detail:
                failure_message += f" Upstream detail: {upstream_detail}"
            elif upstream_message and upstream_message.lower() == "provider returned error":
                failure_message += f" OpenRouter reported: {upstream_message}"
            raise ApplicationError(
                message=failure_message,
                code="openrouter_provider_failed",
                status_code=503 if retryable else 502,
                details={
                    "upstream_status": status_code,
                    "model": model,
                    "retryable": retryable,
                    **(
                        {"upstream_provider": upstream_provider}
                        if upstream_provider
                        else {}
                    ),
                    **(
                        {"upstream_message": upstream_message}
                        if upstream_message
                        else {}
                    ),
                    **(
                        {"upstream_detail": upstream_detail}
                        if upstream_detail
                        else {}
                    ),
                    **({"retry_after": retry_after} if retry_after else {}),
                },
            ) from exc
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                message="OpenRouter chat request timed out.",
                code="openrouter_provider_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc
        except httpx.RequestError as exc:
            raise ApplicationError(
                message="Could not connect to OpenRouter chat inference.",
                code="openrouter_provider_failed",
                status_code=503,
                details={"retryable": True},
            ) from exc

        try:
            response_payload = response.json()
            generated_text = response_payload["choices"][0]["message"]["content"]
            if not isinstance(generated_text, str) or not generated_text.strip():
                raise ValueError("response text is empty")

            usage = response_payload.get("usage") or {}
            input_tokens = usage.get("prompt_tokens")
            output_tokens = usage.get("completion_tokens")
            total_tokens = usage.get("total_tokens")
            if total_tokens is None and (
                input_tokens is not None or output_tokens is not None
            ):
                total_tokens = (input_tokens or 0) + (output_tokens or 0)
            input_tokens = int(input_tokens) if input_tokens is not None else None
            output_tokens = int(output_tokens) if output_tokens is not None else None
            total_tokens = int(total_tokens) if total_tokens is not None else None
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ApplicationError(
                message="OpenRouter returned an invalid chat response.",
                code="openrouter_llm_invalid_response",
                status_code=502,
            ) from exc

        return LlmGenerationResult(
            text=generated_text.strip(),
            model=str(response_payload.get("model") or model),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=(time.perf_counter() - started_at) * 1000,
        )