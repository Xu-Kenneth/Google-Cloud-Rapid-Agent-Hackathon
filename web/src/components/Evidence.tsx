import type { EvidencePayload } from "../types";

export default function Evidence({ data }: { data: EvidencePayload }) {
  return (
    <div className="evidence">
      <div className="evidence__head">
        <div className="evidence__name">
          {data.company_name || data.ticker}
          <b>{data.ticker}</b>
        </div>
        <span className="chip">source · {data.data_source}</span>
      </div>
      <div className="evidence__grid">
        {data.items.map((it, i) => (
          <div className="evidence__item" key={it.id} style={{ animationDelay: `${i * 40}ms` }}>
            <span className="eid">{it.id}</span>
            <span className="etext">{it.text}</span>
          </div>
        ))}
      </div>
      {data.notes?.length > 0 && <div className="note">{data.notes.join("  ·  ")}</div>}
    </div>
  );
}
