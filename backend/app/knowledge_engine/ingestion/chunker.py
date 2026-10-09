from __future__ import annotations

from app.knowledge_engine.shared.models import DocumentChunk


class IntelligentChunkGenerator:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
        if chunk_size < 1:
            raise ValueError("chunk_size must be greater than zero.")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be between zero and chunk_size - 1.")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def generate(
        self,
        text: str | None = None,
        **kwargs,
    ) -> list[DocumentChunk]:
        # If text is not provided directly, try to extract it from kwargs
        if text is None:
            # Try common patterns the pipeline might use
            text = kwargs.get("text")
            if text is None:
                document = kwargs.get("document")
                if document is not None:
                    # Extract text from document object
                    text = getattr(document, "content", None)
                    if text is None:
                        text = getattr(document, "text", None)
            
            if text is None:
                # Last resort: use the entire kwargs as a dict and look for content
                text = kwargs.get("content", "")
        
        if not text:
            return []  # Return empty list if no text to chunk

        document_id = kwargs.get("document_id")
        metadata = kwargs.get("metadata", {})
        chunks: list[DocumentChunk] = []
        normalized_text = text.strip()
        start = 0

        while start < len(normalized_text):
            end = min(start + self.chunk_size, len(normalized_text))
            if end < len(normalized_text):
                preferred_start = start + self.chunk_size // 2
                sentence_boundary = max(
                    normalized_text.rfind(". ", preferred_start, end),
                    normalized_text.rfind("! ", preferred_start, end),
                    normalized_text.rfind("? ", preferred_start, end),
                )
                if sentence_boundary > start:
                    end = sentence_boundary + 1
                else:
                    whitespace_boundary = normalized_text.rfind(
                        " ",
                        preferred_start,
                        end,
                    )
                    if whitespace_boundary > start:
                        end = whitespace_boundary

            chunk_text = normalized_text[start:end].strip()
            if chunk_text:
                chunk_metadata = dict(metadata) if metadata else {}
                if document_id:
                    chunk_metadata["document_id"] = str(document_id)

                chunk_id_prefix = f"{document_id}-" if document_id else ""
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{chunk_id_prefix}chunk-{len(chunks)}",
                        content=chunk_text,
                        metadata=chunk_metadata,
                    )
                )

            if end >= len(normalized_text):
                break

            next_start = max(start + 1, end - self.chunk_overlap)
            next_whitespace = normalized_text.find(" ", next_start, end)
            start = next_whitespace + 1 if next_whitespace >= 0 else next_start

        return chunks