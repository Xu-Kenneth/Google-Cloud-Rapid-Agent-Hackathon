"""Tests for the market-data tool using a mocked HTTP transport (no live calls)."""

import httpx
import pytest

from app.tools import market_data
from app.tools.market_data import EvidencePack, Fundamentals, Quote, fetch_evidence

# --------------------------------------------------------------------------- #
# Finnhub mock
# --------------------------------------------------------------------------- #
_FINNHUB_RESPONSES = {
    "/api/v1/quote": {"c": 100.5, "d": 1.5, "dp": 1.52, "h": 101, "l": 99, "pc": 99.0},
    "/api/v1/stock/profile2": {
        "name": "Test Corp",
        "currency": "USD",
        "marketCapitalization": 2000.0,
    },
    "/api/v1/stock/metric": {
        "metric": {
            "peTTM": 25.0,
            "epsTTM": 4.0,
            "52WeekHigh": 120.0,
            "52WeekLow": 80.0,
            "beta": 1.1,
        }
    },
    "/api/v1/company-news": [
        {
            "headline": "Test Corp beats earnings",
            "source": "Reuters",
            "url": "https://example.com/a",
            "datetime": 1_700_000_000,
        },
        {"headline": "Analyst upgrade", "source": "Bloomberg", "datetime": 1_700_100_000},
    ],
}


def _finnhub_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json=_FINNHUB_RESPONSES[request.url.path])


def _mock_client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_finnhub_handler))


def test_finnhub_path_builds_pack():
    with _mock_client() as client:
        pack = fetch_evidence("aapl", finnhub_api_key="test-key", client=client)

    assert pack.source == "finnhub"
    assert pack.ticker == "AAPL"  # normalized to upper
    assert pack.company_name == "Test Corp"
    assert pack.quote.price == 100.5
    assert pack.quote.percent_change == 1.52
    assert pack.fundamentals.pe_ratio == 25.0
    assert len(pack.news) == 2
    assert pack.news[0].source == "Reuters"
    # First news item should carry an ISO date derived from the unix timestamp.
    assert pack.news[0].published is not None


def test_finnhub_empty_quote_falls_back_to_yfinance(monkeypatch):
    def _bad_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/v1/quote":
            return httpx.Response(200, json={"c": 0})  # no price -> raises
        return httpx.Response(200, json={})

    fallback = EvidencePack(ticker="TSLA", company_name="Tesla", source="yfinance")
    monkeypatch.setattr(market_data, "_from_yfinance", lambda t: fallback)

    with httpx.Client(transport=httpx.MockTransport(_bad_handler)) as client:
        pack = fetch_evidence("TSLA", finnhub_api_key="test-key", client=client)

    assert pack.source == "yfinance"
    assert pack.company_name == "Tesla"


def test_both_providers_fail_returns_limited(monkeypatch):
    def _boom(_ticker):
        raise RuntimeError("offline")

    monkeypatch.setattr(market_data, "_from_yfinance", _boom)

    pack = fetch_evidence("NVDA")  # no finnhub key -> straight to yfinance -> fails

    assert pack.source == "limited"
    assert pack.is_empty()
    assert pack.notes  # carries an explanatory caveat
    assert pack.citable_items() == []


def test_citable_items_are_enumerated_and_prompt_block_renders():
    pack = EvidencePack(
        ticker="MSFT",
        company_name="Microsoft",
        quote=Quote(price=400.0, percent_change=-0.5),
        fundamentals=Fundamentals(market_cap=3_000_000, pe_ratio=35.0),
    )
    items = pack.citable_items()
    ids = [it["id"] for it in items]

    assert ids == ["E1", "E2", "E3"]  # price, market cap, P/E
    block = pack.as_prompt_block()
    assert "Microsoft (MSFT)" in block
    assert "E1:" in block
