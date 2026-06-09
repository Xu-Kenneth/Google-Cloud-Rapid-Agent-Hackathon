"""LLM-as-judge evaluations for debates (Arize Phoenix)."""

from app.evals.debate_evals import (
    EvalResult,
    evaluate_argument,
    evaluate_debate,
    evaluate_verdict,
    gemini_eval_fn,
    record_evals_as_spans,
)

__all__ = [
    "EvalResult",
    "evaluate_argument",
    "evaluate_verdict",
    "evaluate_debate",
    "record_evals_as_spans",
    "gemini_eval_fn",
]
