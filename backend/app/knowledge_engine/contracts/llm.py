from __future__ import annotations

from abc import ABC, abstractmethod


class LlmContract(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float | None = None,
    ) -> str:
        raise NotImplementedError