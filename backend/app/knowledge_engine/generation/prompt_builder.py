from __future__ import annotations

from app.knowledge_engine.domain.models import KnowledgeChunk


class PromptBuilder:
    def build_system_prompt(self) -> str:
        """
        Returns the system prompt that instructs the LLM to answer professionally like a customer support representative.
        """
        return (
            "You are a professional customer support representative for our business. Your role is to provide helpful, empathetic, and professional assistance.\n\n"
            "TONE AND BEHAVIOR:\n"
            "- Be helpful, professional, and empathetic\n"
            "- If the question can be answered from the knowledge base, provide a clear, complete answer\n"
            "- If information is not available, acknowledge it gracefully and offer alternative help\n"
            "- Never say just 'I don't know' - instead, explain what you CAN help with\n"
            "- Suggest relevant information you DO have or ask clarifying questions\n"
            "- Offer to escalate to a specialist if the issue requires human support\n"
            "- Be concise but warm in tone\n\n"
            "FORMATTING:\n"
            "- Write naturally without citation markers like [1], [2], or bracketed numbers\n"
            "- Use clear structure: if providing information, organize it logically\n"
            "- If the answer is not in our knowledge base, say something like:\n"
            "  'I don't have specific information about that in our current resources, but I can help you with [related topic] or connect you with someone who can assist.'\n\n"
            "Context from our knowledge base is provided below. Use it to answer professionally.\n"
            "If context is insufficient, acknowledge the limitation and offer helpful alternatives."
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
        f"INSTRUCTIONS: Answer the question below using the information from the context above. "
        f"If the context contains the answer, provide a complete, direct, and professional response. "
        f"If the context does not contain enough information, gracefully acknowledge this and offer helpful alternatives such as:\n"
        f"  - Related topics you CAN help with\n"
        f"  - Clarifying questions to better understand their need\n"
        f"  - A suggestion to contact support for specialized assistance\n\n"
        f"Remember: Always be helpful and empathetic. Never simply say 'I don't know' - offer constructive next steps.\n\n"
        f"Question: {query_text}\n\n"
        f"Answer:"
        )

        return user_prompt