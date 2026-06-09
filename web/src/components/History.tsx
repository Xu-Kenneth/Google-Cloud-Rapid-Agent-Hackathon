import type { HistorySummary } from "../types";

const pct = (v?: number | null) => (v == null ? "—" : `${Math.round(v)}%`);
const dec = (v?: number | null) => (v == null ? "—" : v.toFixed(2));

interface Props {
  summary: HistorySummary | null;
  loading: boolean;
  onRefresh: () => void;
}

export default function History({ summary, loading, onRefresh }: Props) {
  if (loading) {
    return (
      <div className="empty">
        <div className="big">querying Phoenix…</div>
      </div>
    );
  }
  if (!summary) {
    return (
      <div className="empty">
        <div className="big">History unavailable</div>
        <div>Could not reach the backend.</div>
      </div>
    );
  }

  return (
    <div>
      <div className="stats">
        <div className="stat">
          <b>{summary.total_debates}</b>
          <small>debates</small>
        </div>
        <div className="stat">
          <b>{pct(summary.avg_confidence)}</b>
          <small>avg confidence</small>
        </div>
        <div className="stat">
          <b>{dec(summary.avg_groundedness)}</b>
          <small>avg groundedness</small>
        </div>
        <div className="stat">
          <b>{dec(summary.avg_reasoning)}</b>
          <small>avg reasoning</small>
        </div>
      </div>

      {summary.note && <div className="note">{summary.note}</div>}

      {summary.recent?.length > 0 && (
        <div className="history-rows">
          <div className="hrow head">
            <span>Ticker</span>
            <span>Lean</span>
            <span>Confidence</span>
            <span>Grounded</span>
          </div>
          {summary.recent.map((r, i) => (
            <div className="hrow" key={i}>
              <span className="tk">{r.ticker}</span>
              <span>{r.lean || "—"}</span>
              <span>{pct(r.confidence)}</span>
              <span>{dec(r.groundedness_bull)}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: 18 }}>
        <button className="btn-run" style={{ padding: "11px 22px" }} onClick={onRefresh}>
          Refresh
        </button>
      </div>
    </div>
  );
}
