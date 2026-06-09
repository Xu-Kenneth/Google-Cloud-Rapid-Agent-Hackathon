# Bull vs Bear — Build Checklist

Implementation tracker for the [design spec](docs/superpowers/specs/2026-06-09-bull-vs-bear-design.md).
**Workflow:** each item is one committable unit. When an item is checked, its changes are committed and pushed to `main`.

## Foundation
- [x] **1. Repo scaffolding & license** — `LICENSE` (Apache-2.0), `.gitignore`, `.env.example`, `README.md` skeleton, top-level directory layout.
- [x] **2. Backend project setup** — `backend/pyproject.toml`, `app/config.py` (env-driven settings), FastAPI app with a `/health` route.

## Core capabilities
- [x] **3. Market data tool** — `tools/market_data.py` (Finnhub primary, yfinance fallback) returning a structured evidence pack, with unit tests (mocked APIs).
- [x] **4. Observability setup** — `observability/tracing.py` (Phoenix + OpenInference) and `docker-compose.yml` to run Phoenix locally.
- [x] **5. Debate agents** — `agents/bull.py`, `bear.py`, `judge.py` (Google ADK + Gemini) and `orchestrator.py`, with output-contract tests against a stubbed LLM.
- [x] **6. Debate endpoint (streaming)** — `/debate` SSE route wiring evidence → Bull → Bear → Judge and streaming results to the client.

## Arize core
- [x] **7. Evaluations** — `evals/debate_evals.py`: groundedness eval on Bull/Bear, reasoning-quality eval on the Judge; write scores back as Phoenix span annotations, with a test on canned traces.
- [x] **8. Phoenix MCP integration** — `mcp/phoenix_client.py` + `/history` endpoint reading past-debate performance via the Phoenix MCP server.

## Product surface
- [x] **9. Frontend** — React/Vite app: ticker input, evidence panel, streamed Bull/Bear/Judge view, observability/eval panel, history tab, persistent "not financial advice" banner.
- [x] **10. Firestore persistence** — store debates + scores; back the history view with real data.

## Ship
- [x] **11. Cloud Run deployment** — backend + web Dockerfiles, deploy steps, finalized `README.md` with architecture diagram and run/deploy instructions.
- [x] **12. End-to-end smoke test & polish** — single-ticker E2E against local Phoenix; final cleanup.
