from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, field

from app.infrastructure.observability.tracing import TraceContext, TraceObserver
from app.knowledge_engine.generation.citation_builder import CitationBuilder
from app.knowledge_engine.generation.prompt_builder import PromptBuilder
from app.knowledge_engine.generation.response_formatter import ResponseFormatter
from app.knowledge_engine.generation.response_generator import ResponseGenerator
from app.knowledge_engine.retrieval.conversation_context_builder import (
    ConversationContextBuilder,
)
from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.query_embedder import QueryEmbedder
from app.knowledge_engine.retrieval.reranker import Reranker
from app.knowledge_engine.shared.models import (
    QuestionAnsweringPipelineRequest,
    QuestionAnsweringPipelineResult,
)


@dataclass(slots=True)
class QuestionAnsweringPipeline:
    conversation_context_builder: ConversationContextBuilder
    query_embedder: QueryEmbedder
    hybrid_retriever: HybridRetriever
    metadata_filter: MetadataFilter
    reranker: Reranker
    prompt_builder: PromptBuilder
    response_generator: ResponseGenerator
    citation_builder: CitationBuilder
    response_formatter: ResponseFormatter
    trace_observer: TraceObserver | None = field(default=None)

    def run(
        self,
        request: QuestionAnsweringPipelineRequest,
    ) -> QuestionAnsweringPipelineResult:
        trace_inputs = {
            "application_id": request.application_id,
            "knowledge_base_id": request.knowledge_base_id,
            "conversation_id": request.conversation_id,
            "query_text": request.query_text,
            "top_k": request.top_k,
            "max_context_messages": request.max_context_messages,
            "llm_temperature": request.llm_temperature,
        }
        trace_metadata = {
            "application_id": request.application_id,
            "knowledge_base_id": request.knowledge_base_id,
            "conversation_id": request.conversation_id,
            "request_id": request.request_id,
        }

        trace_context = TraceContext(request_id=request.request_id or "")
        trace_context_manager = (
            self.trace_observer.trace(
                name="question_answering_pipeline",
                run_type="chain",
                inputs=trace_inputs,
                metadata=trace_metadata,
                request_id=request.request_id,
            )
            if self.trace_observer is not None
            else nullcontext(trace_context)
        )

        with trace_context_manager as active_trace_context:
            trace_context = active_trace_context
            conversation_context = self.conversation_context_builder.build(
                request.messages,
                max_messages=request.max_context_messages,
            )
            query_embedding = self.query_embedder.embed(request.query_text)

            # Retrieve MORE chunks initially for better coverage
            initial_top_k = max(request.top_k * 2, 10)  # At least 10, or 2x the final top_k
            retrieved_chunks = self.hybrid_retriever.retrieve(
                knowledge_base_id=request.knowledge_base_id,
                query_text=request.query_text,
                query_embedding=query_embedding,
                top_k=initial_top_k,
            )
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Retrieved {len(retrieved_chunks)} chunks:")
            for i, chunk in enumerate(retrieved_chunks[:5], start=1):
                logger.info(f"[{i}] Score: {chunk.score:.3f}, Title: {chunk.document_title}, Content: {chunk.content[:200]}...")

            filtered_chunks = self.metadata_filter.apply(retrieved_chunks)
            reranked_chunks = self.reranker.rerank(
                query_text=request.query_text,
                chunks=filtered_chunks,
                top_k=request.top_k,
            )

            if not reranked_chunks:
                logger.info(
                    "No relevant chunks retrieved for query '%s'; using safe fallback response.",
                    request.query_text,
                )
                result = self.response_formatter.format(
                    answer_text=(
                        "I can help with questions about our business, but I need a bit more detail to answer accurately. "
                        "Please share the specific issue or question and I’ll help as best I can."
                    ),
                    citations=[],
                    retrieved_chunks=[],
                )
                trace_context.end(
                    outputs={
                        "answer": result.answer_text,
                        "citation_count": 0,
                        "retrieved_chunk_count": 0,
                    }
                )
                return result

            system_prompt = self.prompt_builder.build_system_prompt(
                request.prompt_system_template,
            )
            user_prompt = self.prompt_builder.build_user_prompt(
                query_text=request.query_text,
                conversation_messages=conversation_context,
                retrieved_chunks=reranked_chunks,
            )

            llm_generation = self.response_generator.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=request.llm_temperature,
            )
            citations = self.citation_builder.build(reranked_chunks)

            result = self.response_formatter.format(
                answer_text=llm_generation.text,
                citations=citations,
                retrieved_chunks=reranked_chunks,
                llm_generation=llm_generation,
            )
            trace_context.end(
                outputs={
                    "answer": result.answer_text,
                    "citation_count": len(result.citations),
                    "retrieved_chunk_count": len(result.retrieved_chunks),
                    "model": llm_generation.model,
                    "usage": {
                        "input_tokens": llm_generation.input_tokens,
                        "output_tokens": llm_generation.output_tokens,
                        "total_tokens": llm_generation.total_tokens,
                    },
                    "latency_ms": llm_generation.latency_ms,
                }
            )
            return result