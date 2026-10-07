from __future__ import annotations

from dataclasses import dataclass

from app.config.settings import ProviderSettings


@dataclass(frozen=True, slots=True)
class ActiveProviders:
    llm: str
    embeddings: str
    vector: str
    storage: str


def build_active_providers(settings: ProviderSettings) -> ActiveProviders:
    return ActiveProviders(
        llm=settings.llm,
        embeddings=settings.embeddings,
        vector=settings.vector,
        storage=settings.storage,
    )