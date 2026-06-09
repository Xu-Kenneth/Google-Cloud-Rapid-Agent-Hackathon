"""Arize Phoenix tracing setup via OpenInference + OpenTelemetry.

Design rule: **observability must never block the product.** Every step here is
wrapped so that a missing dependency or an unreachable Phoenix collector degrades
to a logged warning and a ``False`` return — the debate still runs.

All heavy imports are deferred into functions so importing this module is always
safe, even in a minimal environment without Phoenix installed.
"""

from __future__ import annotations

import logging
from typing import Any

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

_initialized = False


def setup_tracing(settings: Settings | None = None) -> bool:
    """Register the Phoenix tracer provider and instrument the agent libraries.

    Returns ``True`` if tracing was enabled, ``False`` if it was skipped/failed.
    Idempotent: safe to call more than once.
    """
    global _initialized
    if _initialized:
        return True

    settings = settings or get_settings()

    try:
        from phoenix.otel import register

        tracer_provider = register(
            project_name=settings.phoenix_project_name,
            endpoint=f"{settings.phoenix_collector_endpoint.rstrip('/')}/v1/traces",
            set_global_tracer_provider=True,
            batch=True,
        )
    except Exception as exc:  # noqa: BLE001 - fail open
        logger.warning(
            "Phoenix tracing unavailable (%s); continuing without tracing.", exc
        )
        return False

    _instrument_libraries(tracer_provider)
    _initialized = True
    logger.info(
        "Phoenix tracing enabled -> %s (project=%s)",
        settings.phoenix_collector_endpoint,
        settings.phoenix_project_name,
    )
    return True


def _instrument_libraries(tracer_provider: Any) -> None:
    """Best-effort OpenInference instrumentation of the agent libraries."""
    for label, factory in (
        ("google-adk", _adk_instrumentor),
        ("google-genai", _genai_instrumentor),
    ):
        try:
            instrumentor = factory()
            if instrumentor is not None:
                instrumentor.instrument(tracer_provider=tracer_provider)
                logger.info("Instrumented %s for tracing.", label)
        except Exception as exc:  # noqa: BLE001 - fail open per library
            logger.warning("Could not instrument %s: %s", label, exc)


def _adk_instrumentor() -> Any | None:
    try:
        from openinference.instrumentation.google_adk import GoogleADKInstrumentor

        return GoogleADKInstrumentor()
    except Exception:  # noqa: BLE001
        return None


def _genai_instrumentor() -> Any | None:
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor

        return GoogleGenAIInstrumentor()
    except Exception:  # noqa: BLE001
        return None


def get_tracer(name: str = "bull-vs-bear") -> Any:
    """Return an OpenTelemetry tracer, or a no-op tracer if OTel is unavailable.

    Lets call sites use ``with get_tracer().start_as_current_span(...)`` whether or
    not tracing is actually wired up.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:  # noqa: BLE001
        return _NoopTracer()


class _NoopSpan:
    def __enter__(self) -> "_NoopSpan":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def set_attribute(self, *_args: object, **_kwargs: object) -> None:
        pass

    def set_status(self, *_args: object, **_kwargs: object) -> None:
        pass

    def record_exception(self, *_args: object, **_kwargs: object) -> None:
        pass


class _NoopTracer:
    """Minimal stand-in so span-context usage never crashes without OTel."""

    def start_as_current_span(self, *_args: object, **_kwargs: object) -> _NoopSpan:
        return _NoopSpan()
