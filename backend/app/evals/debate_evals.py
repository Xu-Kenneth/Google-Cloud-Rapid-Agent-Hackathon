"""LLM-as-judge evaluations that score a debate's quality.

Two evals, run with Gemini as the judge:

* **Groundedness** of each analyst argument against the evidence pack.
* **Reasoning quality** of the Judge's verdict given the arguments and evidence.

Scores are emitted back to Arize Phoenix as span attributes. As with tracing, this
is fail-open: a missing model or collector degrades to a logged note, never an error
that breaks the debate.

The model call is injected as ``eval_fn`` so the scoring logic is unit-testable
without a live LLM.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from pydantic import BaseModel, field_validator

from app.agents.base import parse_json_object
from app.agents.schemas import Argument, Verdict
from app.observability import get_tracer
from app.tools.market_data import EvidencePack

logger = logging.getLogger(__name__)

# (system_instruction, user_prompt) -> JSON text
EvalFn = Callable[[str, str], Awaitable[str]]


class EvalResult(BaseModel):
    """One evaluation outcome."""

    name: str
    score: float  # 0.0 - 1.0
    label: str
    explanation: str = ""


class _RawEval(BaseModel):
    """The shape the judge model is asked to emit."""

    score: float
    label: str = ""
    explanation: str = ""

    @field_validator("score", mode="before")
    @classmethod
    def _clamp(cls, v: object) -> float:
        try:
            n = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(1.0, n))


_GROUNDEDNESS_SYSTEM = """You are an evaluation judge. Assess how well an equity \
analyst's argument is GROUNDED in the supplied evidence. An argument is grounded when \
its claims are supported by the evidence items and it invents no facts or numbers.

Respond ONLY with JSON:
{"score": <0.0-1.0>, "label": "grounded" | "partially_grounded" | "ungrounded", \
"explanation": "<one sentence>"}"""

_REASONING_SYSTEM = """You are an evaluation judge. Assess the REASONING QUALITY of an \
investment verdict: does the conclusion follow logically from the bull and bear \
arguments and the evidence? Penalize verdicts that ignore the arguments or overreach.

Respond ONLY with JSON:
{"score": <0.0-1.0>, "label": "sound" | "mixed" | "unsound", \
"explanation": "<one sentence>"}"""


def _argument_eval_prompt(evidence: EvidencePack, argument: Argument) -> str:
    claims = "\n".join(
        f"- {p.claim}" + (f" [{p.evidence_id}]" if p.evidence_id else "")
        for p in argument.points
    )
    return (
        f"Evidence:\n{evidence.as_prompt_block()}\n\n"
        f"{argument.stance.upper()} argument thesis: {argument.thesis}\n"
        f"Claims:\n{claims or '(none)'}\n\n"
        f"Score how grounded this argument is in the evidence. JSON only."
    )


def _verdict_eval_prompt(
    evidence: EvidencePack, bull: Argument | None, bear: Argument | None, verdict: Verdict
) -> str:
    return (
        f"Evidence:\n{evidence.as_prompt_block()}\n\n"
        f"Bull thesis: {bull.thesis if bull else '(missing)'}\n"
        f"Bear thesis: {bear.thesis if bear else '(missing)'}\n\n"
        f"Verdict: {verdict.lean} (confidence {verdict.confidence}). "
        f"Rationale: {verdict.rationale}\n\n"
        f"Score the reasoning quality of this verdict. JSON only."
    )


async def evaluate_argument(
    name: str, evidence: EvidencePack, argument: Argument | None, eval_fn: EvalFn
) -> EvalResult:
    if argument is None:
        return EvalResult(name=name, score=0.0, label="no_argument")
    raw_text = await eval_fn(_GROUNDEDNESS_SYSTEM, _argument_eval_prompt(evidence, argument))
    raw = parse_json_object(raw_text, _RawEval)
    assert isinstance(raw, _RawEval)
    return EvalResult(
        name=name, score=raw.score, label=raw.label or "unknown", explanation=raw.explanation
    )


async def evaluate_verdict(
    evidence: EvidencePack,
    bull: Argument | None,
    bear: Argument | None,
    verdict: Verdict | None,
    eval_fn: EvalFn,
) -> EvalResult:
    name = "reasoning_quality"
    if verdict is None:
        return EvalResult(name=name, score=0.0, label="no_verdict")
    raw_text = await eval_fn(
        _REASONING_SYSTEM, _verdict_eval_prompt(evidence, bull, bear, verdict)
    )
    raw = parse_json_object(raw_text, _RawEval)
    assert isinstance(raw, _RawEval)
    return EvalResult(
        name=name, score=raw.score, label=raw.label or "unknown", explanation=raw.explanation
    )


async def evaluate_debate(
    evidence: EvidencePack,
    bull: Argument | None,
    bear: Argument | None,
    verdict: Verdict | None,
    eval_fn: EvalFn,
) -> dict[str, EvalResult]:
    """Run all three evals concurrently and key them by short name."""
    bull_eval, bear_eval, verdict_eval = await asyncio.gather(
        evaluate_argument("groundedness_bull", evidence, bull, eval_fn),
        evaluate_argument("groundedness_bear", evidence, bear, eval_fn),
        evaluate_verdict(evidence, bull, bear, verdict, eval_fn),
    )
    return {"bull": bull_eval, "bear": bear_eval, "judge": verdict_eval}


def record_evals_as_spans(evals: dict[str, EvalResult]) -> None:
    """Write eval scores back to Phoenix as span attributes (best-effort)."""
    try:
        tracer = get_tracer("bull-vs-bear.evals")
        with tracer.start_as_current_span("debate.evaluation") as span:
            for ev in evals.values():
                span.set_attribute(f"eval.{ev.name}.score", ev.score)
                span.set_attribute(f"eval.{ev.name}.label", ev.label)
    except Exception as exc:  # noqa: BLE001 - fail open
        logger.warning("Could not record evals to Phoenix: %s", exc)


def gemini_eval_fn(settings) -> EvalFn:
    """Build the production eval function backed by Gemini (google-genai)."""

    async def _eval(system: str, prompt: str) -> str:
        from app.agents.runtime import configure_genai_env

        configure_genai_env(settings)
        from google import genai

        client = genai.Client()
        resp = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        )
        return resp.text or ""

    return _eval
