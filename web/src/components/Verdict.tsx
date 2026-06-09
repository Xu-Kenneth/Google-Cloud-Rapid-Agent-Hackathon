import type { Verdict as V } from "../types";

export default function Verdict({ verdict }: { verdict: V }) {
  const lean = (verdict.lean || "neutral").toLowerCase();
  const conf = Math.max(0, Math.min(100, verdict.confidence ?? 50));
  // Position the marker: bullish pushes right, bearish pushes left, scaled by confidence.
  const pos =
    lean === "bullish" ? 50 + conf / 2 : lean === "bearish" ? 50 - conf / 2 : 50;

  return (
    <div className="verdict">
      <div className="verdict__top">
        <div className={`verdict__lean lean--${lean}`}>{verdict.lean}</div>
        <div className="verdict__conf">
          <b>{conf}%</b>
          <small>confidence</small>
        </div>
      </div>
      <div className="meter">
        <div className="meter__mark" style={{ left: `${pos}%` }} />
      </div>
      <div className="meter__scale">
        <span>Bearish</span>
        <span>Neutral</span>
        <span>Bullish</span>
      </div>
      <p className="verdict__rationale">{verdict.rationale}</p>
      {verdict.key_factors?.length > 0 && (
        <div className="factors">
          {verdict.key_factors.map((f, i) => (
            <span className="f" key={i}>
              {f}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
