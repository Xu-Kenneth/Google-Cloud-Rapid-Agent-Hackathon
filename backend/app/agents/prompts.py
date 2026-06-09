"""User-prompt builders that inject the evidence pack into each agent turn.

Kept separate and pure so prompt construction is easy to test and reason about.
"""

from __future__ import annotations

from app.agents.schemas import Argument
from app.tools.market_data import EvidencePack


def analyst_prompt(evidence: EvidencePack, side: str) -> str:
    """Prompt for the Bull/Bear analyst, grounded in the evidence pack."""
    return (
        f"Stock under review: {evidence.company_name or evidence.ticker} "
        f"({evidence.ticker}).\n\n"
        f"Evidence:\n{evidence.as_prompt_block()}\n\n"
        f"Make the strongest grounded {side} case. Cite evidence ids where possible. "
        f"Respond with JSON only."
    )


def judge_prompt(
    evidence: EvidencePack, bull: Argument | None, bear: Argument | None
) -> str:
    """Prompt for the Judge, combining evidence and both arguments."""
    parts = [
        f"Stock under review: {evidence.company_name or evidence.ticker} "
        f"({evidence.ticker}).",
        "",
        f"Evidence:\n{evidence.as_prompt_block()}",
        "",
        "Bull argument:",
        _render_argument(bull),
        "",
        "Bear argument:",
        _render_argument(bear),
        "",
        "Weigh both sides on how well they are grounded in the evidence and return "
        "your verdict as JSON only.",
    ]
    return "\n".join(parts)


def _render_argument(arg: Argument | None) -> str:
    if arg is None:
        return "(no argument was produced)"
    lines = [f"Thesis: {arg.thesis}"]
    for p in arg.points:
        cite = f" [{p.evidence_id}]" if p.evidence_id else ""
        lines.append(f"- {p.claim}{cite}")
    return "\n".join(lines)
