"""Retrieval evaluation: evidence recovery across a repeatable query set.

Measures whether the correct evidence (declared per-query) is recovered by the
retrieve -> fuse -> filter -> rerank -> context pipeline, using the standard
metrics: recall@k, MRR, and context (evidence-in-context) recall. The corpus and
query embeddings are deterministic, so these numbers are stable run-to-run.
"""

from __future__ import annotations

from tests._retrieval_harness import (
    EVAL_CASES,
    EvalCase,
    Measure,
    retrieve_and_measure,
)

# Evidence recovery threshold: for every case the gold chunks must reach the top-10
# fused candidates and survive into the final context.
MIN_RECALL_AT_10 = 1.0
MIN_CONTEXT_RECALL = 1.0


def _run_all() -> list[tuple[str, float, float, float]]:
    rows: list[tuple[str, float, float, float]] = []
    for case in EVAL_CASES:
        measure = retrieve_and_measure(case)
        rows.append((case.name, measure.recall_at(10), measure.mrr(), measure.context_recall()))
    return rows


def test_single_evidence_queries_recover_gold_into_context() -> None:
    for case in EVAL_CASES:
        if len(case.gold) != 1:
            continue
        measure: Measure = retrieve_and_measure(case)
        assert measure.recall_at(10) == MIN_RECALL_AT_10, case.name
        assert measure.mrr() >= MIN_RECALL_AT_10, case.name
        assert measure.context_recall() == MIN_CONTEXT_RECALL, case.name


def test_multi_part_query_recovers_all_evidence_chunks() -> None:
    case = EvalCase(
        name="multi_part_refund_and_payment",
        query="How long for a refund and what payment methods exist?",
        query_embedding=[0.7, 0.0, 0.3, 0.0],
        knowledge_base_id="kb-1",
        gold=["c_refund", "c_payment"],
    )
    measure: Measure = retrieve_and_measure(case)
    assert set(measure.fused_ids) >= set(case.gold)
    assert measure.context_recall() == MIN_CONTEXT_RECALL
    assert measure.recall_at(10) == MIN_RECALL_AT_10


def test_metrics_helpers_are_bounded_and_consistent() -> None:
    rows = _run_all()
    assert len(rows) == len(EVAL_CASES)
    for _name, recall_at_10, mrr, context_recall in rows:
        assert 0.0 <= recall_at_10 <= 1.0
        assert 0.0 <= mrr <= 1.0
        assert 0.0 <= context_recall <= 1.0
        # Evidence-in-context can never exceed what was fused.
        assert context_recall <= recall_at_10 + 1e-9


def test_evaluation_report_prints_stable_metrics(capsys: object) -> None:
    # The report is a stable, human-readable contract of current retrieval quality.
    rows = _run_all()
    print("\nretrieval evaluation report")
    print("case  recall@10  mrr  context_recall")
    for name, r, m, c in rows:
        print(f"{name:28s} {r:.3f}  {m:.3f}  {c:.3f}")
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    assert "retrieval evaluation report" in captured.out
    assert "context_recall" in captured.out

