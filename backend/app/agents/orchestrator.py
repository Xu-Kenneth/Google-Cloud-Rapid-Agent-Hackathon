"""Debate orchestration: sequence Bull, Bear, and Judge into a result.

The orchestrator is decoupled from the model via an injectable ``run_fn`` so the
debate flow can be tested deterministically with a stub. In production the default
path runs each agent through Google ADK (:mod:`app.agents.runtime`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

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

    def __init__(self, run_fn: RunFn | None = None, settings: Settings | None = None):
        self._run_fn = run_fn
        self._settings = settings or get_settings()

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

        return DebateResult(
            ticker=evidence.ticker,
            company_name=evidence.company_name,
            data_source=evidence.source,
            evidence=evidence.citable_items(),
            bull=bull,
            bear=bear,
            verdict=verdict,
            notes=notes,
        )
