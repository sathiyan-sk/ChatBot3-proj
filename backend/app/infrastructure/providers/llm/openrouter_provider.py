from __future__ import annotations

from dataclasses import dataclass, field
import time

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class OpenRouterLlmProvider(LlmProvider):
    settings: object
    fallback_models: tuple[str, ...] = field(default_factory=tuple)

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

        primary_model = getattr(
            self.settings,
            "model",
            "",
        )

        # Primary model first, then any configured fallbacks. Free-tier
        # models are frequently rate-limited upstream, so falling back to
        # alternates keeps chat working instead of returning 502.
        models: list[str] = []
        if primary_model:
            models.append(primary_model)
        models.extend(self.fallback_models)

        if not models:
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

        last_error: str = "no models attempted"
        started_at = time.perf_counter()

        for model in models:
            payload = {
                "model": model,
                "messages": messages,
                "temperature": effective_temperature,
                "stream": False,
            }

            try:
                response = httpx.post(
                    f"{base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=timeout,
                )
            except httpx.HTTPError as exc:
                last_error = f"{model}: network error ({exc})"
                continue

            if response.status_code == 200:
                try:
                    response_payload = response.json()
                    generated_text = (
                        response_payload["choices"][0]
                        ["message"]["content"]
                    )
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    last_error = f"{model}: invalid response shape"
                    continue

                if isinstance(generated_text, str) and generated_text.strip():
                    usage = response_payload.get("usage") or {}
                    input_tokens = usage.get("prompt_tokens")
                    output_tokens = usage.get("completion_tokens")
                    total_tokens = usage.get("total_tokens")
                    if total_tokens is None and (
                        input_tokens is not None or output_tokens is not None
                    ):
                        total_tokens = (input_tokens or 0) + (output_tokens or 0)

                    return LlmGenerationResult(
                        text=generated_text.strip(),
                        model=str(response_payload.get("model") or model),
                        input_tokens=(
                            int(input_tokens) if input_tokens is not None else None
                        ),
                        output_tokens=(
                            int(output_tokens) if output_tokens is not None else None
                        ),
                        total_tokens=(
                            int(total_tokens) if total_tokens is not None else None
                        ),
                        latency_ms=(time.perf_counter() - started_at) * 1000,
                    )

                last_error = f"{model}: empty response text"
                continue

            # 429 (rate limited), 404 (model gone), 5xx (provider issue)
            # are all worth retrying with the next fallback model.
            last_error = (
                f"{model}: HTTP {response.status_code} "
                f"{response.text[:200]}"
            )

        raise ApplicationError(
            message=(
                "OpenRouter LLM provider request failed. "
                f"Tried models: {last_error}"
            ),
            code="openrouter_provider_failed",
            status_code=502,
        )