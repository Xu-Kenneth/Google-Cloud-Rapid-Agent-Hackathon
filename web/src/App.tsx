import { useEffect, useRef, useState } from "react";
import TickerTape from "./components/TickerTape";
import CommandBar from "./components/CommandBar";
import Evidence from "./components/Evidence";
import Arena from "./components/Arena";
import Verdict from "./components/Verdict";
import Evals from "./components/Evals";
import History from "./components/History";
import { fetchHistory, streamDebate } from "./api";
import type {
  Argument,
  DebateEvals,
  EvidencePayload,
  HistorySummary,
  Phase,
  Verdict as VerdictT,
} from "./types";

const REPO = "https://github.com/Xu-Kenneth/Google-Cloud-Rapid-Agent-Hackathon";

export default function App() {
  const [tab, setTab] = useState<"debate" | "history">("debate");
  const [ticker, setTicker] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [statusMsg, setStatusMsg] = useState("");

  const [evidence, setEvidence] = useState<EvidencePayload | null>(null);
  const [bull, setBull] = useState<Argument | null>(null);
  const [bear, setBear] = useState<Argument | null>(null);
  const [bullErr, setBullErr] = useState<string | null>(null);
  const [bearErr, setBearErr] = useState<string | null>(null);
  const [verdict, setVerdict] = useState<VerdictT | null>(null);
  const [evals, setEvals] = useState<DebateEvals | null>(null);
  const cancelRef = useRef<null | (() => void)>(null);

  const [history, setHistory] = useState<HistorySummary | null>(null);
  const [histLoading, setHistLoading] = useState(false);

  const run = () => {
    const t = ticker.trim().toUpperCase();
    if (!t) return;
    cancelRef.current?.();
    setPhase("fetching");
    setStatusMsg("");
    setEvidence(null);
    setBull(null);
    setBear(null);
    setBullErr(null);
    setBearErr(null);
    setVerdict(null);
    setEvals(null);

    cancelRef.current = streamDebate(t, {
      onStatus: (d) => setStatusMsg(d.message),
      onEvidence: (d) => {
        setEvidence(d);
        setPhase("debating");
      },
      onArgument: (d) => {
        if (d.stance === "bull") {
          setBull(d.argument);
          setBullErr(d.error);
        } else {
          setBear(d.argument);
          setBearErr(d.error);
        }
      },
      onVerdict: (d) => setVerdict(d.verdict),
      onEvals: (d) => setEvals(d.evals),
      onComplete: () => setPhase("complete"),
      onError: () => setPhase((p) => (p === "complete" ? p : "error")),
    });
  };

  useEffect(() => () => cancelRef.current?.(), []);

  const loadHistory = () => {
    setHistLoading(true);
    fetchHistory()
      .then(setHistory)
      .catch(() => setHistory(null))
      .finally(() => setHistLoading(false));
  };
  useEffect(() => {
    if (tab === "history" && !history) loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab]);

  const debating = phase === "fetching" || phase === "debating";
  const bullPending = phase === "debating" && bull === null && !bullErr;
  const bearPending = phase === "debating" && bear === null && !bearErr;

  return (
    <>
      <TickerTape />
      <div className="shell">
        <header className="masthead">
          <div>
            <h1 className="wordmark">
              <span className="bull">Bull</span>
              <span className="v">vs</span>
              <span className="bear">Bear</span>
            </h1>
            <p>Three Gemini agents debate a stock — every claim traced &amp; scored by Arize Phoenix.</p>
          </div>
          <nav className="tabs">
            <button className={tab === "debate" ? "active" : ""} onClick={() => setTab("debate")}>
              Debate
            </button>
            <button className={tab === "history" ? "active" : ""} onClick={() => setTab("history")}>
              History
            </button>
          </nav>
        </header>

        {tab === "debate" ? (
          <>
            <CommandBar value={ticker} onChange={setTicker} onRun={run} disabled={debating} />

            {phase === "error" && (
              <div className="note">
                Couldn’t reach the debate service. Make sure the backend is running and
                <code> VITE_API_BASE</code> points to it.
              </div>
            )}

            {phase === "idle" && !evidence && (
              <div className="empty">
                <div className="big">“The market is a debate. Let’s hear both sides.”</div>
                <div>Enter a ticker above to convene the floor.</div>
              </div>
            )}

            {phase === "fetching" && (
              <div className="empty">
                <div className="big">{statusMsg || "Fetching market data…"}</div>
              </div>
            )}

            {evidence && (
              <>
                <div className="eyebrow">Evidence</div>
                <Evidence data={evidence} />

                <div className="eyebrow">The Floor</div>
                <Arena
                  bull={bull}
                  bear={bear}
                  bullPending={bullPending}
                  bearPending={bearPending}
                  bullErr={bullErr}
                  bearErr={bearErr}
                />

                {(verdict || phase === "complete") && (
                  <>
                    <div className="eyebrow">Verdict</div>
                    {verdict ? (
                      <Verdict verdict={verdict} />
                    ) : (
                      <div className="note">No verdict was reached.</div>
                    )}
                  </>
                )}

                {evals && (
                  <>
                    <div className="eyebrow">Observability · Arize Phoenix</div>
                    <Evals evals={evals} />
                  </>
                )}
              </>
            )}
          </>
        ) : (
          <>
            <div className="eyebrow">Self-reflection · via Phoenix MCP</div>
            <History summary={history} loading={histLoading} onRefresh={loadHistory} />
          </>
        )}

        <footer className="footer">
          <span>Educational only — not financial advice.</span>
          <span>
            Gemini · Google ADK · Arize Phoenix ·{" "}
            <a href={REPO} target="_blank" rel="noreferrer">
              source
            </a>
          </span>
        </footer>
      </div>
    </>
  );
}
