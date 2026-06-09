"""Tests for debate evaluations with a stubbed judge LLM (no Gemini)."""

import asyncio
import json

from app.evals.debate_evals import (
    EvalResult,
    evaluate_argument,
    evaluate_debate,
    record_evals_as_spans,
)
from app.agents.schemas import Argument, Citation, Verdict
from app.tools.market_data import EvidencePack, Fundamentals, Quote


def _evidence() -> EvidencePack:
    return EvidencePack(
        ticker="NVDA",
        company_name="NVIDIA",
        quote=Quote(price=120.0),
        fundamentals=Fundamentals(pe_ratio=40.0),
        source="finnhub",
    )


def _grounded_argument() -> Argument:
    return Argument(
        stance="bull",
        thesis="Strong growth",
        points=[Citation(claim="High demand", evidence_id="E1")],
    )


def _stub_eval(score: float, label: str):
    async def eval_fn(system: str, prompt: str) -> str:
        return json.dumps({"score": score, "label": label, "explanation": "because"})

    return eval_fn


def test_evaluate_argument_parses_score_and_label():
    result = asyncio.run(
        evaluate_argument(
            "groundedness_bull", _evidence(), _grounded_argument(), _stub_eval(0.9, "grounded")
        )
    )
    assert isinstance(result, EvalResult)
    assert result.name == "groundedness_bull"
    assert result.score == 0.9
    assert result.label == "grounded"


def test_evaluate_argument_handles_missing_argument():
    result = asyncio.run(
        evaluate_argument("groundedness_bear", _evidence(), None, _stub_eval(1.0, "x"))
    )
    assert result.score == 0.0
    assert result.label == "no_argument"


def test_score_is_clamped_to_unit_interval():
    result = asyncio.run(
        evaluate_argument(
            "groundedness_bull", _evidence(), _grounded_argument(), _stub_eval(7.5, "ungrounded")
        )
    )
    assert result.score == 1.0  # clamped


def test_evaluate_debate_returns_three_keyed_results():
    verdict = Verdict(lean="Neutral", confidence=50, rationale="balanced")
    evals = asyncio.run(
        evaluate_debate(
            _evidence(),
            _grounded_argument(),
            Argument(stance="bear", thesis="risk"),
            verdict,
            _stub_eval(0.7, "grounded"),
        )
    )
    assert set(evals.keys()) == {"bull", "bear", "judge"}
    assert evals["judge"].name == "reasoning_quality"


def test_record_evals_as_spans_never_raises():
    evals = {"bull": EvalResult(name="groundedness_bull", score=0.8, label="grounded")}
    # Must not raise even without a live Phoenix/OTel backend.
    record_evals_as_spans(evals)
