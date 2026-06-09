"""Tests for the streaming /debate endpoint with stubbed agents and data."""

import json

import pytest
from fastapi.testclient import TestClient

from app.agents import DebateOrchestrator
from app.agents.base import AgentSpec
from app.main import app, get_evidence_fetcher, get_orchestrator
from app.tools.market_data import EvidencePack, Fundamentals, Quote

_CANNED = {
    "bull_analyst": json.dumps(
        {"stance": "bull", "thesis": "growth", "points": [{"claim": "x", "evidence_id": "E1"}]}
    ),
    "bear_analyst": json.dumps(
        {"stance": "bear", "thesis": "valuation", "points": [{"claim": "y", "evidence_id": "E2"}]}
    ),
    "judge": json.dumps(
        {"lean": "Neutral", "confidence": 55, "rationale": "balanced", "key_factors": ["a"]}
    ),
}


async def _run_fn(spec: AgentSpec, prompt: str) -> str:
    return _CANNED[spec.name]


def _fake_fetch(symbol: str) -> EvidencePack:
    return EvidencePack(
        ticker=symbol,
        company_name="NVIDIA",
        quote=Quote(price=120.0, percent_change=2.0),
        fundamentals=Fundamentals(pe_ratio=40.0),
        source="finnhub",
    )


@pytest.fixture
def client():
    app.dependency_overrides[get_orchestrator] = lambda: DebateOrchestrator(run_fn=_run_fn)
    app.dependency_overrides[get_evidence_fetcher] = lambda: _fake_fetch
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_debate_stream_emits_all_event_types(client):
    resp = client.get("/debate", params={"ticker": "nvda"})
    assert resp.status_code == 200
    text = resp.text
    for token in (
        "event: status",
        "event: evidence",
        "event: argument",
        "event: verdict",
        "event: complete",
    ):
        assert token in text, f"missing {token}"
    assert '"stance": "bull"' in text
    assert '"stance": "bear"' in text
    assert '"lean": "Neutral"' in text


def test_debate_rejects_invalid_ticker(client):
    resp = client.get("/debate", params={"ticker": "@@@"})
    assert resp.status_code == 400
