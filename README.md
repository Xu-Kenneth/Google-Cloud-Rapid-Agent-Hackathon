# Bull vs Bear 🐂🐻

> An **observable, multi-agent equity debate** — three Gemini agents argue a stock, and every step is traced and evaluated with Arize Phoenix.

Built for the **Google Cloud Rapid Agent Hackathon — Arize Track**.

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](./LICENSE)
[![Gemini](https://img.shields.io/badge/LLM-Gemini-4285F4.svg)](https://ai.google.dev/)
[![Arize Phoenix](https://img.shields.io/badge/Observability-Arize_Phoenix-7C3AED.svg)](https://phoenix.arize.com/)

> ⚠️ **Educational use only — not financial advice.** Bull vs Bear generates AI
> opinions for demonstration purposes. Do not make investment decisions based on
> its output.

---

## What it does

Enter a stock ticker (e.g. `NVDA`) and watch three autonomous agents debate it:

- 🐂 **Bull** — argues the long case, citing real market evidence.
- 🐻 **Bear** — argues the short case, citing real market evidence.
- ⚖️ **Judge** — weighs both sides into a balanced verdict with a confidence rating.

Because the output is financial and high-stakes, **observability is the product, not
an add-on**: every agent turn streams into Arize Phoenix, each argument is scored for
**groundedness** against the supplied evidence, the Judge's reasoning is evaluated for
quality, and a **History** view queries past-debate performance through the **Phoenix
MCP server**.

## How it works

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
│  mcp/            → Phoenix MCP server (history view)       │
└────────────────────────────────────────────────────────────┘
                │
        Firestore (debate + score history)   •   Phoenix (OSS, docker)
```

**One debate, end to end:** validate ticker → fetch an evidence pack (quote,
fundamentals, news) → Bull argues → Bear argues → Judge decides → all spans traced to
Phoenix → groundedness/reasoning evals scored and annotated → persisted → streamed to
the UI with a link into the Phoenix trace tree.

## Why Arize (the track story)

Arize Phoenix is wired in three ways, each doing real work:

1. **Tracing** — the full multi-agent span tree (every agent + tool call) via
   OpenInference, so you can see exactly what each agent did.
2. **Evaluation** — LLM-as-judge evals gate quality: groundedness on Bull/Bear,
   reasoning quality on the Judge.
3. **MCP server** — the History view asks Phoenix, through its **Model Context
   Protocol server**, how grounded and confident past debates have been.

## Tech stack

| Layer | Choice |
|-------|--------|
| Agents | Google **ADK** (Agent Development Kit) — core of Vertex AI Agent Builder |
| LLM | **Gemini** (via Google AI Studio *or* Vertex AI) |
| Backend | **FastAPI** on **Cloud Run** |
| Frontend | **React + Vite** |
| Observability | **Arize Phoenix** (OSS) — tracing, evals, MCP server |
| Market data | **Finnhub** (free) with **yfinance** fallback |
| Persistence | local file *or* **Firestore** |

Everything is **Google Cloud + Arize only** — no competing cloud or observability tools.

## Project structure

```
bull-vs-bear/
├── LICENSE                 # Apache-2.0
├── README.md
├── CHECKLIST.md            # build tracker
├── .env.example            # environment template (copy to .env)
├── docker-compose.yml      # local Phoenix + backend
├── docs/superpowers/specs/ # design spec
├── backend/
│   └── app/
│       ├── main.py             # FastAPI routes (/debate, /history, /health)
│       ├── config.py           # env-driven settings
│       ├── agents/             # bull, bear, judge, orchestrator
│       ├── tools/              # market_data
│       ├── observability/      # Phoenix / OpenInference tracing
│       ├── evals/              # debate evaluations
│       └── mcp/                # Phoenix MCP client
└── web/                        # React/Vite app
```

## Getting started

### Prerequisites

- **Python 3.11+** and **Node 18+**
- **Docker** (to run Phoenix locally)
- A **Gemini API key** — see step 1

### 1. Configure environment

```bash
cp .env.example .env
```

Open `.env` and provide, at minimum, a Gemini key:

- **Easiest:** get a free **Google AI Studio** key at
  <https://aistudio.google.com/app/apikey>, keep `GOOGLE_GENAI_USE_VERTEXAI=false`,
  and paste it into `GOOGLE_API_KEY`.
- **Vertex AI (Google Cloud):** set `GOOGLE_GENAI_USE_VERTEXAI=true`, fill
  `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION`, and run
  `gcloud auth application-default login`.

Optionally add a free `FINNHUB_API_KEY` for richer market data — otherwise the app
falls back to **yfinance**, which needs no key.

> `.env` is gitignored and must never be committed.

### 2. Start Phoenix (observability)

```bash
docker compose up -d phoenix
```

Phoenix UI: <http://localhost:6006>

### 3. Run the backend

```bash
cd backend
pip install -e .
uvicorn app.main:app --reload --port 8000
```

Health check: <http://localhost:8000/health>

### 4. Run the frontend

```bash
cd web
npm install
npm run dev
```

App: <http://localhost:5173>

## Configuration reference

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GOOGLE_GENAI_USE_VERTEXAI` | yes | `false` | `false` = AI Studio, `true` = Vertex AI |
| `GOOGLE_API_KEY` | if AI Studio | — | AI Studio Gemini key |
| `GOOGLE_CLOUD_PROJECT` | if Vertex | — | GCP project id |
| `GOOGLE_CLOUD_LOCATION` | if Vertex | `us-central1` | Vertex region |
| `GEMINI_MODEL` | no | `gemini-2.5-flash` | Model id |
| `FINNHUB_API_KEY` | no | — | Market data (yfinance fallback if blank) |
| `PHOENIX_COLLECTOR_ENDPOINT` | no | `http://localhost:6006` | Phoenix collector |
| `PHOENIX_PROJECT_NAME` | no | `bull-vs-bear` | Phoenix project |
| `HISTORY_BACKEND` | no | `local` | `local` or `firestore` |
| `BACKEND_HOST` / `BACKEND_PORT` | no | `0.0.0.0` / `8000` | Server bind |
| `CORS_ALLOW_ORIGINS` | no | `http://localhost:5173` | Allowed frontend origins |

## Deployment (Cloud Run)

The backend and web app each ship a `Dockerfile` and deploy to **Cloud Run**.
Full deploy steps are documented as part of the build (see `CHECKLIST.md`, item 11).

## Development

```bash
cd backend
pytest            # run the test suite
```

## License

Licensed under the [Apache License 2.0](./LICENSE).
