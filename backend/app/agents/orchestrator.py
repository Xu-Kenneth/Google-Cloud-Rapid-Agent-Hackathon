"""Debate orchestration: sequence Bull, Bear, and Judge into a result.

The orchestrator is decoupled from the model via an injectable ``run_fn`` so the
debate flow can be tested deterministically with a stub. In production the default
path runs each agent through Google ADK (:mod:`app.agents.runtime`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, AsyncIterator, Awaitable, Callable

if TYPE_CHECKING:
    from app.evals.debate_evals import EvalFn

from app.agents.base import AgentSpec
from app.agents.bear import BEAR
from app.agents.bull import BULL
from app.agents.judge import JUDGE
from app.agents.prompts import analyst_prompt, judge_prompt
from app.agents.schemas import Argument, DebateResult, Verdict
from app.config import Settings, get_settings
from app.tools.market_data import EvidencePack

logger = logging.getLogger(__name__)

RunFn = Callable[[AgentSpec, str], Awaitable[str]]


class DebateOrchestrator:
    """Run a single-pass Bull -> Bear -> Judge debate over an evidence pack."""

    def __init__(
        self,
        run_fn: RunFn | None = None,
        settings: Settings | None = None,
        evaluator: "EvalFn | None" = None,
    ):
        self._run_fn = run_fn
        self._settings = settings or get_settings()
        self._evaluator = evaluator

    async def _evaluate(
        self,
        evidence: EvidencePack,
        bull: Argument | None,
        bear: Argument | None,
        verdict: Verdict | None,
        notes: list[str],
    ) -> dict[str, dict] | None:
        """Run evals if an evaluator is configured (best-effort)."""
        if self._evaluator is None:
            return None
        try:
            from app.evals import evaluate_debate, record_evals_as_spans

            evals = await evaluate_debate(evidence, bull, bear, verdict, self._evaluator)
            record_evals_as_spans(evals)
            return {k: v.model_dump() for k, v in evals.items()}
        except Exception as exc:  # noqa: BLE001 - evals never break the debate
            logger.warning("evaluation failed: %s", exc)
            notes.append(f"evals failed: {exc}")
            return None

    async def _run(self, spec: AgentSpec, prompt: str) -> str:
        if self._run_fn is not None:
            return await self._run_fn(spec, prompt)
        from app.agents.runtime import run_agent

        return await run_agent(spec, prompt, self._settings)

    async def run_argument(
        self, spec: AgentSpec, evidence: EvidencePack, side: str
    ) -> tuple[Argument | None, str | None]:
        """Run one analyst; return (argument, error_note)."""
        try:
            text = await self._run(spec, analyst_prompt(evidence, side))
            arg = spec.parse(text)
            assert isinstance(arg, Argument)
            return arg, None
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("%s agent failed: %s", spec.name, exc)
            return None, f"{spec.name} failed: {exc}"

    async def run_verdict(
        self, evidence: EvidencePack, bull: Argument | None, bear: Argument | None
    ) -> tuple[Verdict | None, str | None]:
        """Run the Judge; return (verdict, error_note)."""
        try:
            text = await self._run(JUDGE, judge_prompt(evidence, bull, bear))
            verdict = JUDGE.parse(text)
            assert isinstance(verdict, Verdict)
            return verdict, None
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("judge failed: %s", exc)
            return None, f"judge failed: {exc}"

    async def run_debate(self, evidence: EvidencePack) -> DebateResult:
        """Run the full debate and assemble a :class:`DebateResult`."""
        notes = list(evidence.notes)

        (bull, bull_err), (bear, bear_err) = await asyncio.gather(
            self.run_argument(BULL, evidence, "bullish"),
            self.run_argument(BEAR, evidence, "bearish"),
        )
        notes += [n for n in (bull_err, bear_err) if n]

        verdict, verdict_err = await self.run_verdict(evidence, bull, bear)
        if verdict_err:
            notes.append(verdict_err)

        evals = await self._evaluate(evidence, bull, bear, verdict, notes)

        return DebateResult(
            ticker=evidence.ticker,
            company_name=evidence.company_name,
            data_source=evidence.source,
            evidence=evidence.citable_items(),
            bull=bull,
            bear=bear,
            verdict=verdict,
            evals=evals,
            notes=notes,
        )

    async def stream_debate(
        self, evidence: EvidencePack
    ) -> AsyncIterator[dict[str, object]]:
        """Yield debate events as they happen, for server-sent streaming.

        Event ``type`` values: ``evidence`` -> ``argument`` (bull) ->
        ``argument`` (bear) -> ``verdict`` -> ``complete``.
        """
        notes = list(evidence.notes)

        yield {
            "type": "evidence",
            "ticker": evidence.ticker,
            "company_name": evidence.company_name,
            "data_source": evidence.source,
            "items": evidence.citable_items(),
            "notes": notes,
        }

        # Start both analysts concurrently; emit each as it resolves.
        bull_task = asyncio.create_task(self.run_argument(BULL, evidence, "bullish"))
        bear_task = asyncio.create_task(self.run_argument(BEAR, evidence, "bearish"))

        bull, bull_err = await bull_task
        if bull_err:
            notes.append(bull_err)
        yield {
            "type": "argument",
            "stance": "bull",
            "argument": bull.model_dump() if bull else None,
            "error": bull_err,
        }

        bear, bear_err = await bear_task
        if bear_err:
            notes.append(bear_err)
        yield {
            "type": "argument",
            "stance": "bear",
            "argument": bear.model_dump() if bear else None,
            "error": bear_err,
        }

        verdict, verdict_err = await self.run_verdict(evidence, bull, bear)
        if verdict_err:
            notes.append(verdict_err)
        yield {
            "type": "verdict",
            "verdict": verdict.model_dump() if verdict else None,
            "error": verdict_err,
        }

        evals = await self._evaluate(evidence, bull, bear, verdict, notes)
        if evals is not None:
            yield {"type": "evals", "evals": evals}

        result = DebateResult(
            ticker=evidence.ticker,
            company_name=evidence.company_name,
            data_source=evidence.source,
            evidence=evidence.citable_items(),
            bull=bull,
            bear=bear,
            verdict=verdict,
            evals=evals,
            notes=notes,
        )
        yield {"type": "complete", "result": result.model_dump()}
