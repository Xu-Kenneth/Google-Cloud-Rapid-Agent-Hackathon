"""Debate agents: Bull, Bear, Judge, and the orchestrator that sequences them."""

from app.agents.bear import BEAR
from app.agents.bull import BULL
from app.agents.judge import JUDGE
from app.agents.orchestrator import DebateOrchestrator
from app.agents.schemas import Argument, Citation, DebateResult, Verdict

__all__ = [
    "BULL",
    "BEAR",
    "JUDGE",
    "DebateOrchestrator",
    "Argument",
    "Citation",
    "Verdict",
    "DebateResult",
]
