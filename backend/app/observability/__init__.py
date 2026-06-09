"""Observability: Arize Phoenix tracing wiring."""

from app.observability.tracing import get_tracer, setup_tracing

__all__ = ["get_tracer", "setup_tracing"]
