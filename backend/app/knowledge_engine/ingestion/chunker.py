from __future__ import annotations

from app.knowledge_engine.shared.models import DocumentChunk, DocumentSection


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
        document = kwargs.get("document")
        structured_sections = getattr(document, "structured_sections", [])
        if structured_sections:
            return self._generate_structured_chunks(
                structured_sections=structured_sections,
                document_id=document_id,
                metadata=metadata,
            )

        chunks: list[DocumentChunk] = []
        normalized_text = text.strip()
        for chunk_text in self._split_text(normalized_text):
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

        return chunks

    def _generate_structured_chunks(
        self,
        *,
        structured_sections: list[DocumentSection],
        document_id: str | None,
        metadata: dict[str, str],
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for section in structured_sections:
            heading = section.heading.strip()
            heading_prefix = ""
            if heading and len(heading) + 1 < self.chunk_size:
                heading_prefix = f"{heading}\n"
            elif heading and self.chunk_size > 5:
                heading_limit = self.chunk_size - 5
                heading_prefix = f"{heading[:heading_limit].rstrip()}...\n"
            max_body_size = max(1, self.chunk_size - len(heading_prefix))

            for body in self._split_text(
                section.content.strip(),
                chunk_size=max_body_size,
            ):
                chunk_metadata = dict(metadata) if metadata else {}
                if document_id:
                    chunk_metadata["document_id"] = str(document_id)
                if heading:
                    chunk_metadata["section_heading"] = heading
                    chunk_metadata["section_level"] = str(section.level)

                chunk_id_prefix = f"{document_id}-" if document_id else ""
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{chunk_id_prefix}chunk-{len(chunks)}",
                        content=f"{heading_prefix}{body}" if heading else body,
                        metadata=chunk_metadata,
                    )
                )

        return chunks

    def _split_text(
        self,
        text: str,
        *,
        chunk_size: int | None = None,
    ) -> list[str]:
        size = chunk_size or self.chunk_size
        chunks: list[str] = []
        start = 0

        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                preferred_start = start + size // 2
                sentence_boundary = max(
                    text.rfind(". ", preferred_start, end),
                    text.rfind("! ", preferred_start, end),
                    text.rfind("? ", preferred_start, end),
                )
                if sentence_boundary > start:
                    end = sentence_boundary + 1
                else:
                    whitespace_boundary = text.rfind(
                        " ",
                        preferred_start,
                        end,
                    )
                    if whitespace_boundary > start:
                        end = whitespace_boundary

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= len(text):
                break

            next_start = max(start + 1, end - self.chunk_overlap)
            next_whitespace = text.find(" ", next_start, end)
            start = next_whitespace + 1 if next_whitespace >= 0 else next_start

        return chunks