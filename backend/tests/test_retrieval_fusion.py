from __future__ import annotations

from typing import override

from app.knowledge_engine.contracts.vector_store import VectorStoreContract
from app.knowledge_engine.retrieval.context_builder import ContextBuilder
from app.knowledge_engine.retrieval.fusion import ReciprocalRankFusion
from app.knowledge_engine.retrieval.metadata_filter import MetadataFilter
from app.knowledge_engine.retrieval.reranker import Reranker
from app.knowledge_engine.shared.models import RetrievedChunk


def _chunk(
    *,
    chunk_id: str,
    document_id: str,
    document_title: str = "doc",
    content: str = "",
    score: float = 0.0,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        document_id=document_id,
        document_title=document_title,
        content=content,
        score=score,
        source_uri=None,
        metadata={},
    )


class _FakeVectorStore(VectorStoreContract):
    def __init__(
        self,
        *,
        semantic: list[RetrievedChunk] | None = None,
        keyword: list[RetrievedChunk] | None = None,
    ) -> None:
        self.semantic_results = list(semantic or [])
        self.keyword_results = list(keyword or [])
        self.similarity_search_calls = 0
        self.keyword_search_calls = 0

    def index_chunk(  # noqa: D401
        self, *, chunk_id: str, content: str, embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        raise NotImplementedError

    @override
    def similarity_search(
        self, *, knowledge_base_id: str, query_embedding: list[float], top_k: int,
    ) -> list[RetrievedChunk]:
        self.similarity_search_calls += 1
        _ = (knowledge_base_id, query_embedding)
        return list(self.semantic_results)

    @override
    def keyword_search(
        self, *, knowledge_base_id: str, query_text: str, top_k: int,
    ) -> list[RetrievedChunk]:
        self.keyword_search_calls += 1
        _ = (knowledge_base_id, query_text)
        return list(self.keyword_results)


def test_fusion_dedupes_and_ranks_overlapping_chunks() -> None:
    fusion = ReciprocalRankFusion(rrf_k=60)
    a = _chunk(chunk_id="c1", document_id="d1")
    b = _chunk(chunk_id="c2", document_id="d1")
    c = _chunk(chunk_id="c3", document_id="d1")
    d = _chunk(chunk_id="c4", document_id="d1")
    # A is rank1(semantic)+rank3(keyword); B is rank2+rank1 -> B first, then A.
    # C is rank3 (semantic only) -> 1/(k+3); D is rank2 (keyword only) ->
    # 1/(k+2), so D outranks C under reciprocal-rank fusion.
    fused = fusion.fuse(
        semantic_chunks=[a, b, c], keyword_chunks=[b, d, a], top_k=10,
    )
    ids = [chunk.chunk_id for chunk in fused]
    assert ids == ["c2", "c1", "c4", "c3"]
    assert ids.index("c2") < ids.index("c3")
    assert ids.index("c1") < ids.index("c4")


def test_fusion_respects_top_k() -> None:
    fusion = ReciprocalRankFusion()
    semantic = [_chunk(chunk_id=str(i), document_id="d1") for i in range(5)]
    keyword = [_chunk(chunk_id=str(i + 100), document_id="d1") for i in range(5)]
    fused = fusion.fuse(semantic_chunks=semantic, keyword_chunks=keyword, top_k=3)
    assert len(fused) == 3


def test_fusion_handles_empty_lists() -> None:
    fusion = ReciprocalRankFusion()
    x = _chunk(chunk_id="x", document_id="d1")
    assert fusion.fuse(semantic_chunks=[], keyword_chunks=[], top_k=5) == []
    # Fusion rewrites each chunk's retrieval score to its RRF score, so compare
    # by chunk_id rather than whole-chunk equality in the single-list cases.
    fused_kw = fusion.fuse(semantic_chunks=[], keyword_chunks=[x], top_k=5)
    assert [c.chunk_id for c in fused_kw] == ["x"]
    fused_sem = fusion.fuse(semantic_chunks=[x], keyword_chunks=[], top_k=5)
    assert [c.chunk_id for c in fused_sem] == ["x"]
    assert fusion.fuse(semantic_chunks=[], keyword_chunks=[], top_k=0) == []


def test_reranker_lexical_overlap_boost() -> None:
    reranker = Reranker(lexical_weight=0.4)
    query = "refund policy"
    matching = _chunk(
        chunk_id="m", document_id="d1",
        content="our refund policy states that requests within 30 days are accepted",
        score=0.5,
    )
    off_topic = _chunk(
        chunk_id="o", document_id="d1",
        content="the server rack is mounted in a17u position",
        score=0.5,
    )
    reranked = reranker.rerank(query_text=query, chunks=[off_topic, matching], top_k=2)
    assert [c.chunk_id for c in reranked] == ["m", "o"]


def test_reranker_empty_returns_empty() -> None:
    reranker = Reranker()
    assert reranker.rerank(query_text="x", chunks=[], top_k=5) == []


def test_metadata_filter_dedupes_overlapping_windows() -> None:
    base = "The billing cycle closes at midnight on the last day of each month."
    filter_ = MetadataFilter()
    chunks = [
        _chunk(chunk_id="c1", document_id="d1", content=base),
        _chunk(chunk_id="c2", document_id="d1", content=base + " Additional detail."),
    ]
    result = filter_.apply(chunks)
    assert len(result) == 1
    assert result[0].chunk_id == "c2"


def test_metadata_filter_enforces_min_score() -> None:
    filter_ = MetadataFilter(min_score=0.5)
    above = _chunk(chunk_id="good", document_id="d1", content="relevant", score=0.8)
    below = _chunk(chunk_id="bad", document_id="d1", content="irrelevant", score=0.2)
    result = filter_.apply([above, below])
    assert [c.chunk_id for c in result] == ["good"]


def test_metadata_filter_drops_empty_content() -> None:
    filter_ = MetadataFilter()
    result = filter_.apply([
        _chunk(chunk_id="a", document_id="d1", content="   "),
        _chunk(chunk_id="b", document_id="d1", content="real content"),
        _chunk(chunk_id="c", document_id="d1", content=""),
    ])
    assert [c.chunk_id for c in result] == ["b"]


def test_metadata_filter_retains_distinct_sections_sharing_a_leading_sentence() -> None:
    shared = "The billing cycle closes at midnight on the last day of each month."
    filter_ = MetadataFilter()
    # Two distinct sections that begin with the same sentence but diverge
    # afterwards must BOTH be retained -- collapsing them would discard
    # distinct, actionable evidence.
    a = _chunk(
        chunk_id="a",
        document_id="d1",
        content=shared + " Refunds are accepted within 30 days.",
    )
    b = _chunk(
        chunk_id="b",
        document_id="d1",
        content=shared + " Refunds require a receipt.",
    )
    result = filter_.apply([a, b])
    assert [c.chunk_id for c in result] == ["a", "b"]


def test_metadata_filter_dedup_keeps_more_complete_regardless_of_order() -> None:
    base = "The billing cycle closes at midnight on the last day of each month."
    filter_ = MetadataFilter()
    short = _chunk(chunk_id="short", document_id="d1", content=base)
    long = _chunk(chunk_id="long", document_id="d1", content=base + " Additional detail.")
    # True overlapping-window sub-windows collapse to the more complete chunk.
    assert [c.chunk_id for c in filter_.apply([short, long])] == ["long"]
    assert [c.chunk_id for c in filter_.apply([long, short])] == ["long"]


def test_context_builder_enforces_max_chunks() -> None:
    builder = ContextBuilder()
    chunks = [_chunk(chunk_id=str(i), document_id="d1", content=f"chunk {i}") for i in range(10)]
    result = builder.build(chunks=chunks, max_chunks=4, max_tokens=None)
    assert len(result) == 4


def test_context_builder_diversity_spans_documents() -> None:
    builder = ContextBuilder(diversity_lambda=0.5)
    chunks = [
        _chunk(chunk_id="a1", document_id="A", content="alpha", score=0.9),
        _chunk(chunk_id="a2", document_id="A", content="alpha two", score=0.8),
        _chunk(chunk_id="b1", document_id="B", content="bravo", score=0.5),
        _chunk(chunk_id="c1", document_id="C", content="charlie", score=0.5),
    ]
    result = builder.build(chunks=chunks, max_chunks=3, max_tokens=None)
    docs = {chunk.document_id for chunk in result}
    assert "B" in docs and "C" in docs
    assert len(result) == 3


def test_context_builder_token_budget_trims_content() -> None:
    builder = ContextBuilder(max_chunk_chars=100_000)
    long_content = "x" * 1000
    chunks = [_chunk(chunk_id=str(i), document_id="d1", content=long_content, score=1.0) for i in range(3)]
    result = builder.build(chunks=chunks, max_chunks=3, max_tokens=20)
    total_chars = sum(len(chunk.content) for chunk in result)
    assert total_chars <= 20 * 4
    assert all(len(chunk.content) <= 1000 for chunk in result)


def test_context_builder_empty_returns_empty() -> None:
    builder = ContextBuilder()
    assert builder.build(chunks=[], max_chunks=5, max_tokens=None) == []


def test_context_builder_trims_oversized_chunks() -> None:
    builder = ContextBuilder(max_chunk_chars=10)
    chunk = _chunk(chunk_id="x", document_id="d1", content="abcdefghij" * 5, score=1.0)
    result = builder.build(chunks=[chunk], max_chunks=1, max_tokens=None)
    assert len(result) == 1
    assert len(result[0].content) == 10


def test_hybrid_retriever_fuses_semantic_and_keyword() -> None:
    from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
    shared = _chunk(chunk_id="shared", document_id="d1", score=0.8)
    only_semantic = _chunk(chunk_id="semantic_only", document_id="d1", score=0.5)
    only_keyword = _chunk(chunk_id="keyword_only", document_id="d1", score=0.5)
    store = _FakeVectorStore(
        semantic=[shared, only_semantic], keyword=[shared, only_keyword],
    )
    retriever = HybridRetriever(vector_store_contract=store)
    results = retriever.retrieve(
        knowledge_base_id="kb-1", query_text="anything",
        query_embedding=[0.0], top_k=3,
    )
    ids = [chunk.chunk_id for chunk in results]
    assert ids[0] == "shared"
    assert set(ids) == {"shared", "semantic_only", "keyword_only"}
    assert store.similarity_search_calls == 1
    assert store.keyword_search_calls == 1


def test_hybrid_retriever_top_k_zero_returns_empty() -> None:
    from app.knowledge_engine.retrieval.hybrid_retriever import HybridRetriever
    store = _FakeVectorStore(semantic=[], keyword=[])
    retriever = HybridRetriever(vector_store_contract=store)
    assert retriever.retrieve(
        knowledge_base_id="kb-1", query_text="x", query_embedding=[0.0], top_k=0,
    ) == []
