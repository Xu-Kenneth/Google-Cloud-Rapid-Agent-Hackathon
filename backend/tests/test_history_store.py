"""Tests for the local history store and result mapping."""

from app.history.store import LocalHistoryStore, record_from_result
from app.mcp import DebateRecord


def test_record_from_result_maps_fields():
    result = {
        "ticker": "NVDA",
        "verdict": {"lean": "Bullish", "confidence": 72},
        "evals": {
            "bull": {"name": "groundedness_bull", "score": 0.9, "label": "grounded"},
            "bear": {"name": "groundedness_bear", "score": 0.6, "label": "partially_grounded"},
            "judge": {"name": "reasoning_quality", "score": 0.8, "label": "sound"},
        },
    }
    rec = record_from_result(result)
    assert rec.ticker == "NVDA"
    assert rec.lean == "Bullish"
    assert rec.confidence == 72
    assert rec.groundedness_bull == 0.9
    assert rec.reasoning_quality == 0.8
    assert rec.timestamp is not None


def test_record_from_result_handles_missing_evals_and_verdict():
    rec = record_from_result({"ticker": "TSLA"})
    assert rec.ticker == "TSLA"
    assert rec.lean is None
    assert rec.groundedness_bull is None


def test_local_store_round_trip_and_summary(tmp_path):
    store = LocalHistoryStore(tmp_path / "history.jsonl")

    # Empty store reports zero with a guiding note.
    empty = store.summarize()
    assert empty.total_debates == 0
    assert empty.source == "local"
    assert empty.note

    store.record(
        DebateRecord(ticker="NVDA", lean="Bullish", confidence=80, groundedness_bull=0.9)
    )
    store.record(
        DebateRecord(ticker="TSLA", lean="Bearish", confidence=40, groundedness_bull=0.5)
    )

    summary = store.summarize()
    assert summary.total_debates == 2
    assert summary.avg_confidence == 60.0
    # Newest first in the recent slice.
    assert summary.recent[0].ticker == "TSLA"


def test_local_store_skips_corrupt_lines(tmp_path):
    path = tmp_path / "history.jsonl"
    store = LocalHistoryStore(path)
    store.record(DebateRecord(ticker="NVDA", confidence=50))
    with path.open("a", encoding="utf-8") as fh:
        fh.write("this is not json\n")

    summary = store.summarize()
    assert summary.total_debates == 1
