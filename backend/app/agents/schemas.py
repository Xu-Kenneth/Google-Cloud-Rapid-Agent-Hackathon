"""Structured outputs for the debate agents.

These pydantic models are the contract between the agents and the rest of the app.
Agents are instructed to emit JSON matching ``Argument`` / ``Verdict``; the
orchestrator parses into these types and never trusts free-form text.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Citation(BaseModel):
    """A single claim, ideally tied to an evidence item id (e.g. ``E1``)."""

    claim: str
    evidence_id: str | None = None


class Argument(BaseModel):
    """One side's case (bull or bear)."""

    stance: str  # "bull" | "bear"
    thesis: str
    points: list[Citation] = Field(default_factory=list)


class Verdict(BaseModel):
    """The Judge's balanced conclusion."""

    lean: str  # "Bullish" | "Bearish" | "Neutral"
    confidence: int = 50  # 0-100
    rationale: str = ""
    key_factors: list[str] = Field(default_factory=list)

    @field_validator("confidence", mode="before")
    @classmethod
    def _clamp_confidence(cls, v: object) -> int:
        try:
            n = int(round(float(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 50
        return max(0, min(100, n))

    @field_validator("lean", mode="before")
    @classmethod
    def _normalize_lean(cls, v: object) -> str:
        s = str(v or "").strip().lower()
        if any(tok in s for tok in ("bull", "buy", "long", "overweight")):
            return "Bullish"
        if any(tok in s for tok in ("bear", "sell", "short", "underweight")):
            return "Bearish"
        return "Neutral"


class DebateResult(BaseModel):
    """The full result of one debate, assembled by the orchestrator."""

    ticker: str
    company_name: str | None = None
    data_source: str = "limited"
    evidence: list[dict[str, str]] = Field(default_factory=list)
    bull: Argument | None = None
    bear: Argument | None = None
    verdict: Verdict | None = None
    notes: list[str] = Field(default_factory=list)
