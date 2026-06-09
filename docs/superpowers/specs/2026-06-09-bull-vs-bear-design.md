# Bull vs Bear — Design Spec

**Date:** 2026-06-09
**Status:** Approved (brainstorming)
**Event:** Google Cloud Rapid Agent Hackathon (Arize Track)

## 1. Summary

Bull vs Bear is a web application where a user enters a stock ticker and watches
three Gemini agents debate it. A **Bull** agent argues the long case, a **Bear**
agent argues the short case, and a **Judge** agent weighs both arguments into a
balanced verdict with a confidence rating. Arize Phoenix traces the entire
multi-agent exchange, evaluates each side's groundedness against the supplied
evidence, and a History view queries past debates through the Phoenix MCP server.

The product is intentionally small and fully observable: one ticker, one debate,
every step traced and evaluated.

## 2. Goals & Non-Goals

### Goals
- Demonstrate an autonomous multi-agent system built on Gemini + Google ADK
  (the open-source core of Vertex AI Agent Builder).
- Make Arize the structural backbone: tracing (OpenInference → Phoenix), LLM-judge
  evals on every agent, and the Phoenix **MCP server** as the read path for history
  and self-reflection.
- Ship a clean, modular, public-GitHub-ready repository with an Apache-2.0 license.
- Provide a memorable live demo: a streamed three-agent debate with a visible
  observability/eval panel linking into the Phoenix trace tree.

### Non-Goals (YAGNI)
- No user accounts, auth, or multi-tenant concerns.
- No real trading, order placement, brokerage integration, or portfolios.
- No paid/real-time market data feeds.
- No rebuttal round — debate is single-pass (Bull → Bear → Judge).
- No competing cloud (AWS/Azure) or competing observability (Datadog/Dynatrace).

## 3. Tech Constraints (hard guardrails)
- **Compute/hosting:** Google Cloud Run.
- **Agents:** Google ADK (Agent Development Kit) running Gemini on Vertex AI.
  Optional stretch: deploy the orchestrator to Vertex AI Agent Engine.
- **Model:** latest available Gemini (e.g. `gemini-2.x`), via Vertex AI.
- **Storage:** Firestore (debate + score history).
- **Observability/eval:** Arize Phoenix (open source, self-hosted via Docker) with
  OpenInference instrumentation; Phoenix evals; Phoenix MCP server.
- **Market data:** free public API (Finnhub primary, yfinance fallback).
- No non-Google cloud services and no non-Arize observability tools anywhere.

## 4. User Experience / Demo Flow
1. User enters a ticker (e.g. `NVDA`) and clicks **Debate**.
2. **Evidence panel** fills first: latest quote, a few fundamentals, recent
   headlines — the grounding the agents must argue from.
3. **Bull** and **Bear** arguments stream in live, side by side; each point cites
   an evidence item.
4. **Judge** renders a verdict: lean (Bullish / Bearish / Neutral) + confidence %
   + the 2–3 deciding factors.
5. **Observability panel** shows per-agent eval scores (groundedness, reasoning
   quality) with a one-click link into the Phoenix trace tree.
6. **History tab** (Phoenix MCP server): "how grounded/confident have past debates
   been?" — demonstrating the MCP server doing real work.
7. A persistent **"Educational only — not financial advice"** banner is always
   visible.

## 5. Architecture

```
┌── Web (React + Vite) ──────────────┐
│  Debate view (SSE stream)          │  ──► Cloud Run
│  Evidence · Observability · History│
└────────────────────────────────────┘
                │  HTTP / SSE
┌── Backend (FastAPI, Cloud Run) ────────────────────────────┐
│  Orchestrator (Google ADK)                                 │
│   ├─ market_data tool  → free API (Finnhub / yfinance)     │
│   ├─ Bull agent  (Gemini)                                  │
│   ├─ Bear agent  (Gemini)                                  │
│   └─ Judge agent (Gemini)                                  │
│  observability/  → OpenInference → Phoenix (traces)        │
│  evals/          → Phoenix LLM-judge evals (Gemini)        │
│  mcp/            → Phoenix MCP server (history view)        │
└────────────────────────────────────────────────────────────┘
                │
        Firestore (debate + score history)   •   Phoenix (OSS, docker)
```

### Data flow for one debate
1. `POST /debate {ticker}` → backend validates the ticker.
2. `market_data` tool fetches quote + fundamentals + recent news → **evidence pack**.
3. Bull agent produces a long thesis citing evidence items.
4. Bear agent produces a short thesis citing evidence items.
5. Judge agent consumes both theses + evidence → verdict + confidence + key factors.
6. All agent and tool calls emit OpenInference spans to Phoenix.
7. Phoenix evals score Bull/Bear groundedness and Judge reasoning quality; scores
   are written back as span annotations.
8. Debate + scores persisted to Firestore.
9. Results (including a Phoenix trace link) streamed to the UI over SSE.
10. History tab reads aggregate past performance via the Phoenix MCP server.

## 6. Module Layout

```
bull-vs-bear/
├── LICENSE                 # Apache-2.0, repo root
├── README.md               # what/why, architecture diagram, run + deploy steps
├── .env.example            # all required keys documented; no secrets committed
├── docker-compose.yml      # local Phoenix + backend
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI routes (/debate stream, /history)
│   │   ├── config.py               # env-driven settings
│   │   ├── agents/
│   │   │   ├── bull.py
│   │   │   ├── bear.py
│   │   │   ├── judge.py
│   │   │   └── orchestrator.py
│   │   ├── tools/
│   │   │   └── market_data.py      # quote/fundamentals/news → evidence pack
│   │   ├── observability/
│   │   │   └── tracing.py          # Phoenix / OpenInference setup
│   │   ├── evals/
│   │   │   └── debate_evals.py     # eval definitions + runner
│   │   └── mcp/
│   │       └── phoenix_client.py   # talks to the Phoenix MCP server
│   ├── tests/                      # pytest
│   └── pyproject.toml
└── web/                            # React/Vite app
```

Each unit has one purpose and a clear interface:
- `market_data` — given a ticker, return a structured evidence pack; knows nothing
  about agents.
- `agents/*` — each agent takes structured input and produces structured output;
  knows nothing about HTTP or storage.
- `orchestrator` — sequences the agents; the only place debate flow lives.
- `observability/tracing` — wires OpenInference to Phoenix; imported for side effect.
- `evals/debate_evals` — pure eval logic over traces/evidence.
- `mcp/phoenix_client` — wraps Phoenix MCP calls for the history read path.

## 7. Evaluation Strategy (Arize core)
- **Groundedness / hallucination eval** on each Bull and Bear argument against the
  evidence pack (LLM-as-judge using Gemini, executed through Phoenix evals).
- **Reasoning-quality eval** on the Judge verdict: does the conclusion follow from
  the presented arguments?
- Scores are written back as Phoenix span annotations and surfaced in the
  Observability panel.
- The Phoenix **MCP server** is the read path for the History tab and a short
  self-reflection answer (e.g. "past debates averaged X% groundedness").

## 8. Error Handling & Resilience
- **Bad ticker:** validate against the data API up front; return a friendly error.
- **Data API failure:** fall back between Finnhub and yfinance; if both fail, pass
  a "limited data" evidence pack and let agents argue with the caveat — never crash.
- **LLM/agent failure:** retry with exponential backoff; if one side fails, the
  Judge proceeds and notes an incomplete debate.
- **Observability fail-open:** if Phoenix or evals are unavailable, the debate still
  runs; the panel shows "trace/eval unavailable." Observability must never block the
  core product.
- **Eval failure:** show "eval pending/unavailable" rather than erroring the debate.

## 9. Testing
- Unit tests for `market_data` (mocked API responses) and evidence shaping.
- Output-contract tests for each agent against a stubbed LLM (output structure,
  citations present, verdict fields populated).
- Eval-module test with canned traces/evidence.
- One end-to-end smoke test (single ticker) against a locally running Phoenix.

## 10. Open Questions / Risks
- ADK ↔ Phoenix instrumentation maturity: confirm the OpenInference instrumentor
  for Google ADK/GenAI covers our agent calls; fall back to manual spans if needed.
- Free data API rate limits: cache evidence per ticker for the demo session.
- Vertex AI access/quota for Gemini must be set up before the build.

## 11. License
Apache-2.0, file present at repo root, referenced in the README.
