export interface EvidenceItem {
  id: string;
  text: string;
}

export interface Citation {
  claim: string;
  evidence_id?: string | null;
}

export interface Argument {
  stance: string;
  thesis: string;
  points: Citation[];
}

export interface Verdict {
  lean: string;
  confidence: number;
  rationale: string;
  key_factors: string[];
}

export interface EvalResult {
  name: string;
  score: number;
  label: string;
  explanation?: string;
}

export type DebateEvals = Record<string, EvalResult>;

export interface EvidencePayload {
  ticker: string;
  company_name?: string | null;
  data_source: string;
  items: EvidenceItem[];
  notes: string[];
}

export interface HistoryRecord {
  ticker: string;
  lean?: string | null;
  confidence?: number | null;
  groundedness_bull?: number | null;
  groundedness_bear?: number | null;
  reasoning_quality?: number | null;
}

export interface HistorySummary {
  source: string;
  total_debates: number;
  avg_confidence?: number | null;
  avg_groundedness?: number | null;
  avg_reasoning?: number | null;
  recent: HistoryRecord[];
  note?: string | null;
}

export type Phase = "idle" | "fetching" | "debating" | "complete" | "error";
