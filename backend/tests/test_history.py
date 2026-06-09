"""Tests for the Phoenix MCP client aggregation and the /history endpoint."""

import pytest
from fastapi.testclient import TestClient

from app.main import app, get_phoenix_client
from app.mcp import DebateRecord, PhoenixMCPClient, summarize_records


def test_summarize_records_aggregates_averages():
    records = [
        DebateRecord(
            ticker="NVDA",
            lean="Bullish",
            confidence=70,
            groundedness_bull=0.9,
            groundedness_bear=0.7,
            reasoning_quality=0.8,
        ),
        DebateRecord(
            ticker="TSLA",
            lean="Bearish",
            confidence=50,
            groundedness_bull=0.5,
            groundedness_bear=0.5,
            reasoning_quality=0.6,
        ),
    ]
    summary = summarize_records(records)

    assert summary.source == "phoenix-mcp"
    assert summary.total_debates == 2
    assert summary.avg_confidence == 60.0
    assert summary.avg_groundedness == 0.65  # mean of 0.9,0.7,0.5,0.5
    assert summary.avg_reasoning == 0.7


def test_summarize_records_handles_empty():
    summary = summarize_records([])
    assert summary.total_debates == 0
    assert summary.avg_confidence is None


def _client_with(fetcher):
    app.dependency_overrides[get_phoenix_client] = lambda: PhoenixMCPClient(
        endpoint="http://localhost:6006", project_name="test", record_fetcher=fetcher
    )
    return TestClient(app)


def test_history_endpoint_returns_summary_from_mcp():
    async def fetcher(_client):
        return [
            DebateRecord(ticker="NVDA", confidence=80, groundedness_bull=0.9, reasoning_quality=0.9)
        ]

    client = _client_with(fetcher)
    try:
        resp = client.get("/history")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "phoenix-mcp"
    assert body["total_debates"] == 1


def test_history_endpoint_fails_open_when_mcp_unavailable():
    async def boom(_client):
        raise RuntimeError("no node / no phoenix")

    client = _client_with(boom)
    try:
        resp = client.get("/history")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "none"
    assert body["total_debates"] == 0
    assert body["note"]
