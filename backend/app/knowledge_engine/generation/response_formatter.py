from __future__ import annotations

from app.knowledge_engine.contracts.llm import LlmGenerationResult
from app.knowledge_engine.shared.models import Citation, QuestionAnsweringPipelineResult, RetrievedChunk


class ResponseFormatter:
    def format(
        self,
        *,
        answer_text: str,
        citations: list[Citation],
        retrieved_chunks: list[RetrievedChunk],
        llm_generation: LlmGenerationResult | None = None,
    ) -> QuestionAnsweringPipelineResult:
        return QuestionAnsweringPipelineResult(
            answer_text=answer_text,
            citations=citations,
            retrieved_chunks=retrieved_chunks,
            llm_generation=llm_generation,
        )