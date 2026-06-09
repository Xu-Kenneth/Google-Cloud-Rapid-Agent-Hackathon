"""FastAPI application entrypoint for Bull vs Bear.

Routes are intentionally thin: they validate input and delegate to the agent
orchestrator, evaluation, and persistence modules added in later build steps.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import run_in_threadpool

from app import __version__
from app.agents import DebateOrchestrator
from app.config import get_settings
from app.evals import gemini_eval_fn
from app.history import HistoryStore, build_history_store, record_from_result
from app.mcp import HistorySummary, PhoenixMCPClient
from app.observability import setup_tracing
from app.tools.market_data import EvidencePack
from app.tools.market_data import fetch_evidence as _fetch_evidence

settings = get_settings()

_TICKER_RE = re.compile(r"[A-Z][A-Z.\-]{0,9}")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Enable Phoenix tracing on startup (fail-open: never blocks serving).
    setup_tracing(settings)
    yield


app = FastAPI(
    title="Bull vs Bear",
    description="Observable multi-agent equity debate powered by Gemini and Arize Phoenix.",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    """Liveness probe and non-secret config summary."""
    return {
        "status": "ok",
        "service": "bull-vs-bear",
        "version": __version__,
        "config": settings.public_status(),
    }


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Bull vs Bear", "docs": "/docs", "health": "/health"}


# --------------------------------------------------------------------------- #
# Debate endpoint
# --------------------------------------------------------------------------- #
def get_orchestrator() -> DebateOrchestrator:
    """Dependency: the debate orchestrator (overridable in tests)."""
    evaluator = gemini_eval_fn(settings) if settings.gemini_configured else None
    return DebateOrchestrator(settings=settings, evaluator=evaluator)


def get_evidence_fetcher() -> Callable[[str], EvidencePack]:
    """Dependency: a fetcher that closes over config (overridable in tests)."""

    def fetch(symbol: str) -> EvidencePack:
        return _fetch_evidence(symbol, finnhub_api_key=settings.finnhub_api_key)

    return fetch


def get_history_store() -> HistoryStore:
    """Dependency: the debate history store (overridable in tests)."""
    return build_history_store(settings)


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload)}


@app.get("/debate")
async def debate(
    ticker: str = Query(..., min_length=1, max_length=12, description="Stock ticker"),
    orchestrator: DebateOrchestrator = Depends(get_orchestrator),
    fetch: Callable[[str], EvidencePack] = Depends(get_evidence_fetcher),
    store: HistoryStore = Depends(get_history_store),
) -> EventSourceResponse:
    """Stream a Bull vs Bear debate for ``ticker`` as Server-Sent Events."""
    symbol = ticker.strip().upper()
    if not _TICKER_RE.fullmatch(symbol):
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")

    async def event_gen():
        yield _sse("status", {"message": f"Fetching market data for {symbol}", "ticker": symbol})
        # Market-data calls are blocking; keep the event loop free.
        evidence = await run_in_threadpool(fetch, symbol)
        async for evt in orchestrator.stream_debate(evidence):
            if evt.get("type") == "complete":
                try:
                    record = record_from_result(evt["result"])
                    await run_in_threadpool(store.record, record)
                except Exception:  # noqa: BLE001 - persistence never breaks the stream
                    pass
            yield _sse(str(evt["type"]), evt)

    return EventSourceResponse(event_gen())


# --------------------------------------------------------------------------- #
# History endpoint (Phoenix MCP)
# --------------------------------------------------------------------------- #
def get_phoenix_client() -> PhoenixMCPClient:
    """Dependency: the Phoenix MCP client (overridable in tests)."""
    return PhoenixMCPClient(
        endpoint=settings.phoenix_collector_endpoint,
        project_name=settings.phoenix_project_name,
    )


@app.get("/history", response_model=HistorySummary)
async def history(
    client: PhoenixMCPClient = Depends(get_phoenix_client),
    store: HistoryStore = Depends(get_history_store),
) -> HistorySummary:
    """Aggregate past-debate performance.

    Prefers the Phoenix MCP server; falls back to the local/Firestore history store
    when MCP is unavailable.
    """
    summary = await client.summarize()
    if summary is not None:
        return summary
    try:
        return await run_in_threadpool(store.summarize)
    except Exception:  # noqa: BLE001 - last-resort fail open
        return HistorySummary(
            source="none",
            total_debates=0,
            recent=[],
            note="History temporarily unavailable.",
        )
