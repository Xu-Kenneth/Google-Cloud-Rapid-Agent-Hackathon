"""FastAPI application entrypoint for Bull vs Bear.

Routes are intentionally thin: they validate input and delegate to the agent
orchestrator, evaluation, and persistence modules added in later build steps.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.config import get_settings
from app.observability import setup_tracing

settings = get_settings()


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
