from __future__ import annotations

import logging
from dataclasses import dataclass

from app.knowledge_engine.contracts.parsing import ParsingContract
from app.knowledge_engine.shared.models import ParsedDocument, RawSource

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class FallbackParsingProvider(ParsingContract):
    primary: ParsingContract
    fallback: ParsingContract

    def parse(self, source: RawSource) -> ParsedDocument:
        try:
            return self.primary.parse(source)
        except Exception:
            logger.warning(
                "Primary parser %s failed for %s; falling back to %s.",
                type(self.primary).__name__,
                source.source_identifier,
                type(self.fallback).__name__,
                exc_info=True,
            )
            return self.fallback.parse(source)