"""Contract tests for the debate agents against a stubbed LLM (no ADK/Gemini)."""

import asyncio
import json

from app.agents import DebateOrchestrator
from app.agents.base import AgentSpec, parse_json_object
from app.agents.bear import BEAR
from app.agents.bull import BULL
from app.agents.judge import JUDGE
from app.agents.prompts import analyst_prompt, judge_prompt
from app.agents.schemas import Argument, Verdict
from app.tools.market_data import EvidencePack, Fundamentals, Quote


def _evidence() -> EvidencePack:
    return EvidencePack(
        ticker="NVDA",
        company_name="NVIDIA",
        quote=Quote(price=120.0, percent_change=2.0),
        fundamentals=Fundamentals(market_cap=3_000_000, pe_ratio=40.0),
        source="finnhub",
    )


def _stub_run_fn(overrides=None):
    """Return a run_fn that emits canned JSON keyed by agent name."""
    responses = {
        "bull_analyst": json.dumps(
            {
                "stance": "bull",
                "thesis": "Dominant AI franchise with pricing power.",
                "points": [{"claim": "High growth", "evidence_id": "E1"}],
            }
        ),
        "bear_analyst": json.dumps(
            {
                "stance": "bear",
                "thesis": "Valuation rich versus durable risk.",
                "points": [{"claim": "Elevated P/E", "evidence_id": "E3"}],
            }
        ),
        "judge": json.dumps(
            {
                "lean": "Neutral",
                "confidence": 62,
                "rationale": "Strong growth offset by valuation.",
                "key_factors": ["growth", "valuation"],
            }
        ),
    }
    responses.update(overrides or {})

    async def run_fn(spec: AgentSpec, prompt: str) -> str:
        return responses[spec.name]

    return run_fn


def test_run_debate_assembles_all_three_sides():
    orch = DebateOrchestrator(run_fn=_stub_run_fn())
    result = asyncio.run(orch.run_debate(_evidence()))

    assert result.ticker == "NVDA"
    assert result.data_source == "finnhub"
    assert result.bull.stance == "bull"
    assert result.bear.stance == "bear"
    assert result.verdict.lean == "Neutral"
    assert result.verdict.confidence == 62
    assert result.evidence  # citable items were attached
    assert result.notes == []


def test_failed_agent_is_noted_but_debate_continues():
    # Bull raises; Bear and Judge return valid canned JSON.
    base = _stub_run_fn()

    async def run_fn(spec: AgentSpec, prompt: str) -> str:
        if spec.name == "bull_analyst":
            raise RuntimeError("model timeout")
        return await base(spec, prompt)

    orch = DebateOrchestrator(run_fn=run_fn)
    result = asyncio.run(orch.run_debate(_evidence()))

    assert result.bull is None
    assert result.bear is not None
    assert result.verdict is not None
    assert any("bull_analyst failed" in n for n in result.notes)


def test_analyst_prompt_includes_evidence_and_ticker():
    prompt = analyst_prompt(_evidence(), "bullish")
    assert "NVDA" in prompt
    assert "E1:" in prompt  # an enumerated evidence id is present
    assert "bullish" in prompt


def test_judge_prompt_includes_both_arguments():
    bull = Argument(stance="bull", thesis="up", points=[])
    bear = Argument(stance="bear", thesis="down", points=[])
    prompt = judge_prompt(_evidence(), bull, bear)
    assert "Bull argument:" in prompt
    assert "Bear argument:" in prompt
    assert "up" in prompt and "down" in prompt


def test_parser_tolerates_code_fences_and_prose():
    raw = "Here is my answer:\n```json\n{\"stance\": \"bull\", \"thesis\": \"t\", \"points\": []}\n```"
    arg = parse_json_object(raw, Argument)
    assert isinstance(arg, Argument)
    assert arg.thesis == "t"


def test_verdict_clamps_confidence_and_normalizes_lean():
    v = parse_json_object(
        json.dumps({"lean": "strong buy", "confidence": 250, "rationale": "x"}), Verdict
    )
    assert v.lean == "Bullish"
    assert v.confidence == 100


def test_agent_specs_have_distinct_names():
    names = {BULL.name, BEAR.name, JUDGE.name}
    assert len(names) == 3
