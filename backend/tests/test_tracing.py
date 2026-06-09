"""Tracing must fail open: never raise, even without Phoenix installed/running."""

from app.observability import tracing
from app.observability.tracing import get_tracer


def test_setup_tracing_never_raises_and_returns_bool():
    result = tracing.setup_tracing()
    assert isinstance(result, bool)


def test_get_tracer_supports_span_context_even_without_otel():
    tracer = get_tracer("test")
    # Whether real or no-op, this usage pattern must not crash.
    with tracer.start_as_current_span("unit-test-span") as span:
        span.set_attribute("k", "v")
