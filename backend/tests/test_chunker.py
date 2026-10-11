from app.knowledge_engine.ingestion.chunker import IntelligentChunkGenerator
from app.knowledge_engine.ingestion.normalizer import DocumentNormalizer
from app.knowledge_engine.shared.models import (
    DocumentSection,
    NormalizedDocument,
    ParsedDocument,
)


def test_long_sentence_is_split_into_bounded_chunks_with_overlap():
    text = "A" * 1200

    chunks = IntelligentChunkGenerator(
        chunk_size=500,
        chunk_overlap=100,
    ).generate(
        text=text,
        document_id="document-id",
    )

    assert [len(chunk.content) for chunk in chunks] == [500, 500, 400]
    assert all(chunk.metadata["document_id"] == "document-id" for chunk in chunks)
    assert [chunk.chunk_id for chunk in chunks] == [
        "document-id-chunk-0",
        "document-id-chunk-1",
        "document-id-chunk-2",
    ]
    assert chunks[0].content[-100:] == chunks[1].content[:100]
    assert chunks[1].content[-100:] == chunks[2].content[:100]


def test_chunk_boundaries_prefer_whitespace_without_exceeding_limit():
    text = "word " * 300

    chunks = IntelligentChunkGenerator(
        chunk_size=100,
        chunk_overlap=20,
    ).generate(text=text)

    assert len(chunks) > 1
    assert all(len(chunk.content) <= 100 for chunk in chunks)
    assert all(chunk.content for chunk in chunks)


def test_invalid_chunk_size_or_overlap_is_rejected():
    try:
        IntelligentChunkGenerator(chunk_size=0)
    except ValueError as exc:
        assert "chunk_size" in str(exc)
    else:
        raise AssertionError("A zero chunk size must be rejected.")

    try:
        IntelligentChunkGenerator(chunk_size=10, chunk_overlap=10)
    except ValueError as exc:
        assert "chunk_overlap" in str(exc)
    else:
        raise AssertionError("Overlap must be smaller than chunk size.")


def test_structured_sections_keep_heading_context_in_bounded_chunks():
    document = NormalizedDocument(
        title="Clinic Guide",
        content="Clinic Guide > Hours\nThe clinic is open Monday through Friday.",
        sections=["The clinic is open Monday through Friday."],
        structured_sections=[
            DocumentSection(
                heading="Clinic Guide > Hours",
                content="The clinic is open Monday through Friday.",
                level=2,
            )
        ],
    )

    chunks = IntelligentChunkGenerator(
        chunk_size=64,
        chunk_overlap=10,
    ).generate(
        document=document,
        document_id="guide",
    )

    assert len(chunks) == 1
    assert chunks[0].content.startswith("Clinic Guide > Hours\n")
    assert chunks[0].metadata["section_heading"] == "Clinic Guide > Hours"
    assert chunks[0].metadata["section_level"] == "2"
    assert len(chunks[0].content) <= 64


def test_normalizer_preserves_docling_table_row_boundaries():
    parsed = ParsedDocument(
        title="Services",
        content="| Service | Hours |\n|---|---|\n| Clinic | 9 to 5 |",
        sections=[],
        structured_sections=[
            DocumentSection(
                heading="Services",
                content="| Service | Hours |\n|---|---|\n| Clinic | 9 to 5 |",
            )
        ],
    )

    normalized = DocumentNormalizer().normalize(parsed)

    assert normalized.structured_sections[0].content.splitlines() == [
        "| Service | Hours |",
        "|---|---|",
        "| Clinic | 9 to 5 |",
    ]
