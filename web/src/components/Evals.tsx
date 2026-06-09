import type { DebateEvals, EvalResult } from "../types";

const PHOENIX_URL =
  (import.meta as any).env?.VITE_PHOENIX_URL ?? "http://localhost:6006";

function scoreColor(score: number): string {
  if (score >= 0.75) return "var(--bull)";
  if (score >= 0.5) return "var(--gold)";
  return "var(--bear)";
}

function EvalCard({ title, ev }: { title: string; ev?: EvalResult }) {
  const score = ev?.score ?? 0;
  const color = scoreColor(score);
  return (
    <div className="evalcard">
      <div className="evalcard__top">
        <span>{title}</span>
        <span>{ev?.name ?? "—"}</span>
      </div>
      <div className="evalcard__score" style={{ color }}>
        {score.toFixed(2)}
      </div>
      <div className="bar">
        <i style={{ width: `${Math.round(score * 100)}%`, background: color }} />
      </div>
      <div className="evalcard__label" style={{ color }}>
        {ev?.label ?? "pending"}
      </div>
    </div>
  );
}

export default function Evals({ evals }: { evals: DebateEvals }) {
  return (
    <>
      <div className="evals">
        <EvalCard title="Bull · grounded" ev={evals.bull} />
        <EvalCard title="Bear · grounded" ev={evals.bear} />
        <EvalCard title="Judge · reasoning" ev={evals.judge} />
      </div>
      <a className="phoenix-link" href={PHOENIX_URL} target="_blank" rel="noreferrer">
        <span className="dot" />
        Open the trace tree in Arize Phoenix →
      </a>
    </>
  );
}
