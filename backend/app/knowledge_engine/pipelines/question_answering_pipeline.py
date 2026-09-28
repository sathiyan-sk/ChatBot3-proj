from __future__ import annotations

from dataclasses import dataclass

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

    def run(
        self,
        request: QuestionAnsweringPipelineRequest,
    ) -> QuestionAnsweringPipelineResult:
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
        # TEMPORARY DEBUG LOGGING
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

        system_prompt = self.prompt_builder.build_system_prompt(
            request.prompt_system_template,
        )
        user_prompt = self.prompt_builder.build_user_prompt(
            query_text=request.query_text,
            conversation_messages=conversation_context,
            retrieved_chunks=reranked_chunks,
        )

        answer_text = self.response_generator.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=request.llm_temperature,
        )
        citations = self.citation_builder.build(reranked_chunks)

        return self.response_formatter.format(
            answer_text=answer_text,
            citations=citations,
            retrieved_chunks=reranked_chunks,
        )