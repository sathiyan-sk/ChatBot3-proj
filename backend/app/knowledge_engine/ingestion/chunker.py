from __future__ import annotations

import re

from app.knowledge_engine.shared.models import DocumentChunk


class IntelligentChunkGenerator:
    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ):
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

        # Extract optional metadata from kwargs
        document_id = kwargs.get("document_id")
        metadata = kwargs.get("metadata", {})

        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks: list[DocumentChunk] = []
        current_chunk_text = ""
        current_chunk_index = 0

        for sentence in sentences:
            if len(current_chunk_text) + len(sentence) <= self.chunk_size:
                current_chunk_text += " " + sentence if current_chunk_text else sentence
            else:
                # Save current chunk
                if current_chunk_text.strip():
                    chunk_metadata = dict(metadata) if metadata else {}
                    if document_id:
                        chunk_metadata["document_id"] = str(document_id)

                    # Chunk IDs must be globally unique: the vector store uses
                    # chunk_id as PRIMARY KEY, so bare "chunk-0" style IDs from
                    # different documents would overwrite each other.
                    chunk_id_prefix = (
                        f"{document_id}-" if document_id else ""
                    )

                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{chunk_id_prefix}chunk-{current_chunk_index}",
                            content=current_chunk_text.strip(),
                            metadata=chunk_metadata,
                        )
                    )
                    current_chunk_index += 1

                # Start new chunk with overlap (last 2-3 sentences)
                overlap_sentences = re.split(r'(?<=[.!?])\s+', current_chunk_text)[-3:]
                current_chunk_text = " ".join(overlap_sentences) + " " + sentence

        # Don't forget the last chunk
        if current_chunk_text.strip():
            chunk_metadata = dict(metadata) if metadata else {}
            if document_id:
                chunk_metadata["document_id"] = str(document_id)

            chunk_id_prefix = (
                f"{document_id}-" if document_id else ""
            )

            chunks.append(
                DocumentChunk(
                    chunk_id=f"{chunk_id_prefix}chunk-{current_chunk_index}",
                    content=current_chunk_text.strip(),
                    metadata=chunk_metadata,
                )
            )

        return chunks