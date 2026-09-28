from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.exceptions import ApplicationError
from app.knowledge_engine.domain.provider_interfaces import LlmProvider


@dataclass(slots=True)
class OllamaLlmProvider(LlmProvider):
    settings: object

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> str:
        normalized_system = system_prompt.strip()
        normalized_user = user_prompt.strip()

        if not normalized_user:
            raise ApplicationError(
                message="LLM user prompt cannot be empty.",
                code="llm_prompt_empty",
                status_code=400,
            )

        base_url = getattr(self.settings, "base_url", "http://127.0.0.1:11434").rstrip("/")
        model = getattr(self.settings, "llm_model_name", "qwen2.5:7b")
        effective_temperature = (
            temperature
            if temperature is not None
            else float(getattr(self.settings, "llm_temperature", 0.2))
        )
        timeout = float(getattr(self.settings, "provider_timeout_seconds", 30.0))

        url = f"{base_url}/api/chat"

        messages: list[dict[str, str]] = []
        if normalized_system:
            messages.append({"role": "system", "content": normalized_system})
        messages.append({"role": "user", "content": normalized_user})

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": effective_temperature,
            },
        }

        try:
            response = httpx.post(
                url,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ApplicationError(
                message="Ollama LLM provider request failed.",
                code="llm_provider_failed",
                status_code=502,
            ) from exc

        response_payload = response.json()
        generated_text = (
            response_payload.get("message", {})
            .get("content", "")
        )

        if not isinstance(generated_text, str) or not generated_text.strip():
            raise ApplicationError(
                message="Ollama provider returned invalid response text.",
                code="llm_provider_invalid_response",
                status_code=502,
            )

        return generated_text.strip()