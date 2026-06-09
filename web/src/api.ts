import type {
  Argument,
  DebateEvals,
  EvidencePayload,
  HistorySummary,
  Verdict,
} from "./types";

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:8000";

export interface DebateHandlers {
  onStatus?: (d: { message: string; ticker: string }) => void;
  onEvidence?: (d: EvidencePayload) => void;
  onArgument?: (d: {
    stance: string;
    argument: Argument | null;
    error: string | null;
  }) => void;
  onVerdict?: (d: { verdict: Verdict | null; error: string | null }) => void;
  onEvals?: (d: { evals: DebateEvals }) => void;
  onComplete?: (d: { result: unknown }) => void;
  onError?: () => void;
}

/** Open an SSE stream for a debate. Returns a cancel function. */
export function streamDebate(ticker: string, handlers: DebateHandlers): () => void {
  const url = `${API_BASE}/debate?ticker=${encodeURIComponent(ticker)}`;
  const es = new EventSource(url);

  const bind = (name: string, cb?: (d: any) => void) =>
    es.addEventListener(name, (e) => {
      try {
        cb?.(JSON.parse((e as MessageEvent).data));
      } catch {
        /* ignore malformed frame */
      }
    });

  bind("status", handlers.onStatus);
  bind("evidence", handlers.onEvidence);
  bind("argument", handlers.onArgument);
  bind("verdict", handlers.onVerdict);
  bind("evals", handlers.onEvals);
  bind("complete", (d) => {
    handlers.onComplete?.(d);
    es.close();
  });

  es.onerror = () => {
    handlers.onError?.();
    es.close();
  };

  return () => es.close();
}

export async function fetchHistory(): Promise<HistorySummary> {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error(`history failed: ${res.status}`);
  return res.json();
}
