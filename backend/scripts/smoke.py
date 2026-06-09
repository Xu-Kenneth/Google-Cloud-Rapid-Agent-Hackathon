"""Live smoke test: run one real debate against Gemini + Phoenix.

Unlike the unit/E2E tests (which stub the model), this calls the real LLM and is
meant to be run by hand once your environment is configured:

    # 1. set GOOGLE_API_KEY (or Vertex AI vars) in ../.env
    # 2. (optional) start Phoenix:  docker compose up -d phoenix
    # 3. install runtime deps:      pip install -e .
    # 4. run:                       python scripts/smoke.py NVDA

It prints the evidence, both arguments, the verdict, and eval scores.
"""

from __future__ import annotations

import asyncio
import sys

from app.agents import DebateOrchestrator
from app.config import get_settings
from app.evals import gemini_eval_fn
from app.observability import setup_tracing
from app.tools.market_data import fetch_evidence


async def main(ticker: str) -> int:
    settings = get_settings()
    if not settings.gemini_configured:
        print("ERROR: Gemini is not configured. Set GOOGLE_API_KEY (or Vertex vars).")
        return 1

    setup_tracing(settings)
    print(f"Fetching evidence for {ticker}...")
    evidence = fetch_evidence(ticker, finnhub_api_key=settings.finnhub_api_key)
    print(evidence.as_prompt_block())
    print("\nConvening the debate (this calls Gemini)...\n")

    evaluator = gemini_eval_fn(settings)
    orchestrator = DebateOrchestrator(settings=settings, evaluator=evaluator)
    result = await orchestrator.run_debate(evidence)

    print(f"🐂 BULL: {result.bull.thesis if result.bull else '(failed)'}")
    print(f"🐻 BEAR: {result.bear.thesis if result.bear else '(failed)'}")
    if result.verdict:
        print(f"\n⚖️  VERDICT: {result.verdict.lean} ({result.verdict.confidence}%)")
        print(f"    {result.verdict.rationale}")
    if result.evals:
        print("\nEvals:")
        for key, ev in result.evals.items():
            print(f"  {key}: {ev['score']:.2f} ({ev['label']})")
    if result.notes:
        print("\nNotes:", "; ".join(result.notes))
    return 0


if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    raise SystemExit(asyncio.run(main(symbol)))
