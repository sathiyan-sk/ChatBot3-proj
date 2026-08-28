from __future__ import annotations

from app.knowledge_engine.domain.models import KnowledgeChunk


class PromptBuilder:
    def build_system_prompt(self) -> str:
        """
        Returns the system prompt that instructs the LLM to answer based only on context.
        """
        return (
                  "You are a helpful assistant. Answer the question below using the provided context.\n"
        "If the context contains relevant information, use it to give a complete answer.\n"
        "Do NOT include citation markers like [1], [2] or any bracketed numbers in your answer - "
        "write naturally in plain prose.\n"
        "If the context truly has no relevant information, you may use your general knowledge to help.\n\n"
        "Context is provided below. Use it to answer the question."
        )

    def build_user_prompt(
        self,
        *,
        query_text: str,
        conversation_messages: list[dict[str, str]] | None = None,
        retrieved_chunks: list[KnowledgeChunk],
    ) -> str:
        """
        Builds the user prompt containing context + question.
        """
        # Build context section with numbered chunks
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(
                f"[{i}] {chunk.content}\n"
                f"   (Source: {chunk.document_title}, Score: {chunk.score:.3f})"
            )

        context_text = "\n\n".join(context_parts)

        # Add conversation history if provided
        conversation_text = ""
        if conversation_messages:
            conversation_parts = []
            for msg in conversation_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                conversation_parts.append(f"{role}: {content}")
            conversation_text = "\n".join(conversation_parts) + "\n\n"

        # Final user prompt
        user_prompt = (
        f"{conversation_text}"
        f"Below is the knowledge base context for answering the question.\n\n"
        f"{context_text}\n\n"
        f"IMPORTANT: Answer the question below using ONLY the information from the context above. "
        f"If the context contains the answer, provide a complete, direct answer. "
        f"If the context does not contain enough information, say so clearly.\n\n"
        f"Question: {query_text}\n\n"
        f"Answer:"
        )

        return user_prompt