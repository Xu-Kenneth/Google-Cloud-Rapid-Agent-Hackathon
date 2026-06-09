import type { Argument } from "../types";

function Thinking({ label }: { label: string }) {
  return (
    <div className="thinking">
      <span className="dots">
        <span />
        <span />
        <span />
      </span>
      {label}
    </div>
  );
}

interface SideProps {
  stance: "bull" | "bear";
  argument: Argument | null;
  pending: boolean;
  error: string | null;
}

function Side({ stance, argument, pending, error }: SideProps) {
  const isBull = stance === "bull";
  return (
    <div className={`side side--${stance}`}>
      <div className="side__head">
        <span className="side__icon">{isBull ? "🐂" : "🐻"}</span>
        {isBull ? "The Bull" : "The Bear"}
      </div>
      {argument ? (
        <>
          <p className="thesis">{argument.thesis}</p>
          {argument.points.map((p, i) => (
            <div className="point" key={i} style={{ animationDelay: `${i * 70}ms` }}>
              {p.evidence_id && <span className="cite">{p.evidence_id}</span>}
              <span>{p.claim}</span>
            </div>
          ))}
        </>
      ) : error ? (
        <div className="note">{error}</div>
      ) : pending ? (
        <Thinking label={isBull ? "building the long case…" : "building the short case…"} />
      ) : (
        <Thinking label="awaiting the floor…" />
      )}
    </div>
  );
}

interface Props {
  bull: Argument | null;
  bear: Argument | null;
  bullPending: boolean;
  bearPending: boolean;
  bullErr: string | null;
  bearErr: string | null;
}

export default function Arena({
  bull,
  bear,
  bullPending,
  bearPending,
  bullErr,
  bearErr,
}: Props) {
  return (
    <div className="arena">
      <Side stance="bull" argument={bull} pending={bullPending} error={bullErr} />
      <div className="seam" />
      <Side stance="bear" argument={bear} pending={bearPending} error={bearErr} />
    </div>
  );
}
