from __future__ import annotations

# Canonical SourceLoader lives in source_loaders/base.py. This module
# re-exports it so older imports keep working against a single class
# hierarchy (avoids duplicate ABCs that break type checking).
from app.knowledge_engine.ingestion.source_loaders.base import SourceLoader

__all__ = ["SourceLoader"]