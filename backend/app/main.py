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
    return DebateOrchestrator(settings=settings)


def get_evidence_fetcher() -> Callable[[str], EvidencePack]:
    """Dependency: a fetcher that closes over config (overridable in tests)."""

    def fetch(symbol: str) -> EvidencePack:
        return _fetch_evidence(symbol, finnhub_api_key=settings.finnhub_api_key)

    return fetch


def _sse(event: str, payload: dict) -> dict:
    return {"event": event, "data": json.dumps(payload)}


@app.get("/debate")
async def debate(
    ticker: str = Query(..., min_length=1, max_length=12, description="Stock ticker"),
    orchestrator: DebateOrchestrator = Depends(get_orchestrator),
    fetch: Callable[[str], EvidencePack] = Depends(get_evidence_fetcher),
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
            yield _sse(str(evt["type"]), evt)

    return EventSourceResponse(event_gen())
