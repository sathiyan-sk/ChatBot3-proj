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
            "- If the knowledge base does not answer the question, do not stop at a refusal or lead with a negative limitation\n"
            "- First provide a concise, useful general explanation based on reliable common knowledge when it is safe and relevant\n"
            "- Clearly label general guidance and never present it as this business's policy, pricing, guarantee, or official process\n"
            "- Do not invent business-specific facts, commitments, contact details, or procedures\n"
            "- Briefly explain that the business-specific detail is not confirmed in the current resources, then ask a focused clarifying question or suggest contacting support\n"
            "- Offer to escalate to a specialist if the issue requires human support\n"
            "- Be concise but warm in tone\n\n"
            "FORMATTING:\n"
            "- Write naturally without citation markers like [1], [2], or bracketed numbers\n"
            "- Use clear structure: if providing information, organize it logically\n"
            "- For an unknown question, use this response shape when appropriate:\n"
            "  1. Give a brief general answer or useful background\n"
            "  2. Say that the business-specific details are not confirmed in the current resources\n"
            "  3. Ask one useful follow-up question or offer a clear support next step\n"
            "- Do not begin with 'I don't know', 'I cannot help', or 'not available' when useful general guidance can be given\n\n"
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
        f"INSTRUCTIONS: Answer the question below using the knowledge base context when it contains the answer. "
        f"If the context contains the answer, provide a complete, direct, and professional response. "
        f"If the context is insufficient, still be useful: provide a concise general explanation when safe and relevant, clearly label it as general guidance, and do not claim it is the business's official policy or process. "
        f"Then briefly state that the business-specific detail is not confirmed in the current resources and offer one practical next step or ask one focused follow-up question. "
        f"Never fabricate missing business facts, and never respond with only 'I don't know' or a bare limitation.\n\n"
        f"Question: {query_text}\n\n"
        f"Answer:"
        )

        return user_prompt