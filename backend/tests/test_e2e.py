"""End-to-end test across the HTTP surface: debate -> record -> history.

Uses the *real* orchestrator, evaluator wiring, history store, and endpoints, with
only the LLM calls and market data stubbed. This exercises the same path a live
debate takes, minus external services.
"""

import json

import pytest
from fastapi.testclient import TestClient

from app.agents import DebateOrchestrator
from app.agents.base import AgentSpec
from app.history import LocalHistoryStore
from app.main import (
    app,
    get_evidence_fetcher,
    get_history_store,
    get_orchestrator,
    get_phoenix_client,
)
from app.mcp import PhoenixMCPClient
from app.tools.market_data import EvidencePack, Fundamentals, Quote

_ARGS = {
    "bull_analyst": {"stance": "bull", "thesis": "growth", "points": [{"claim": "demand", "evidence_id": "E1"}]},
    "bear_analyst": {"stance": "bear", "thesis": "valuation", "points": [{"claim": "rich P/E", "evidence_id": "E3"}]},
    "judge": {"lean": "Bullish", "confidence": 68, "rationale": "growth wins", "key_factors": ["demand"]},
}


async def _run_fn(spec: AgentSpec, prompt: str) -> str:
    return json.dumps(_ARGS[spec.name])


async def _eval_fn(system: str, prompt: str) -> str:
    return json.dumps({"score": 0.82, "label": "grounded", "explanation": "supported"})


def _fake_fetch(symbol: str) -> EvidencePack:
    return EvidencePack(
        ticker=symbol,
        company_name="NVIDIA",
        quote=Quote(price=120.0, percent_change=2.0),
        fundamentals=Fundamentals(market_cap=3_000_000, pe_ratio=40.0),
        source="finnhub",
    )


@pytest.fixture
def client(tmp_path):
    store = LocalHistoryStore(tmp_path / "history.jsonl")

    async def _mcp_unavailable(_c):
        raise RuntimeError("no phoenix mcp in test")

    app.dependency_overrides[get_orchestrator] = lambda: DebateOrchestrator(
        run_fn=_run_fn, evaluator=_eval_fn
    )
    app.dependency_overrides[get_evidence_fetcher] = lambda: _fake_fetch
    app.dependency_overrides[get_history_store] = lambda: store
    app.dependency_overrides[get_phoenix_client] = lambda: PhoenixMCPClient(
        endpoint="x", project_name="t", record_fetcher=_mcp_unavailable
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_full_debate_then_history(client):
    # 1) Run a debate end to end.
    resp = client.get("/debate", params={"ticker": "nvda"})
    assert resp.status_code == 200
    text = resp.text
    for token in ("event: evidence", "event: argument", "event: verdict", "event: evals", "event: complete"):
        assert token in text, f"missing {token}"
    assert '"lean": "Bullish"' in text
    assert '"score": 0.82' in text  # eval scores streamed

    # 2) History reflects the recorded debate (MCP unavailable -> local store).
    hist = client.get("/history")
    assert hist.status_code == 200
    body = hist.json()
    assert body["source"] == "local"
    assert body["total_debates"] == 1
    assert body["recent"][0]["ticker"] == "NVDA"
    assert body["avg_groundedness"] == 0.82
    assert body["avg_confidence"] == 68.0
