"""Persistence for completed debates, backing the History view.

Two interchangeable backends behind one :class:`HistoryStore` protocol:

* :class:`LocalHistoryStore` — append-only JSON Lines file, zero external deps.
* :class:`FirestoreHistoryStore` — Google Cloud Firestore (lazy import).

The History endpoint queries the Phoenix MCP server first; when that is
unavailable it falls back to this store, which holds the app's own record of every
debate and its eval scores.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import threading
from pathlib import Path
from typing import Protocol

from app.config import Settings
from app.mcp.phoenix_client import DebateRecord, HistorySummary, summarize_records

logger = logging.getLogger(__name__)

_RECENT_LIMIT = 50


def record_from_result(result: dict) -> DebateRecord:
    """Map a serialized ``DebateResult`` into a flat :class:`DebateRecord`."""
    evals = result.get("evals") or {}
    verdict = result.get("verdict") or {}

    def score(key: str) -> float | None:
        entry = evals.get(key)
        return entry.get("score") if isinstance(entry, dict) else None

    return DebateRecord(
        ticker=result.get("ticker", "?"),
        lean=verdict.get("lean"),
        confidence=verdict.get("confidence"),
        groundedness_bull=score("bull"),
        groundedness_bear=score("bear"),
        reasoning_quality=score("judge"),
        timestamp=dt.datetime.now(dt.timezone.utc).isoformat(),
    )


def _summary_with_fallback_note(summary: HistorySummary) -> HistorySummary:
    if summary.total_debates == 0:
        summary.note = "No debates recorded yet. Run a debate to populate history."
    return summary


class HistoryStore(Protocol):
    def record(self, record: DebateRecord) -> None: ...

    def summarize(self) -> HistorySummary: ...


class LocalHistoryStore:
    """Append-only JSON Lines store (newest entries summarized first)."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, record: DebateRecord) -> None:
        line = json.dumps(record.model_dump())
        with self._lock:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def _load(self) -> list[DebateRecord]:
        if not self.path.exists():
            return []
        records: list[DebateRecord] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(DebateRecord.model_validate_json(line))
                except Exception:  # noqa: BLE001 - skip corrupt lines
                    continue
        return records

    def summarize(self) -> HistorySummary:
        records = self._load()
        records.reverse()  # newest first for the "recent" slice
        return _summary_with_fallback_note(summarize_records(records, source="local"))


class FirestoreHistoryStore:
    """Firestore-backed store (lazy google-cloud-firestore import)."""

    def __init__(self, project: str, collection: str = "debates"):
        from google.cloud import firestore  # noqa: PLC0415 - optional dependency

        self._client = firestore.Client(project=project)
        self._collection = collection

    def record(self, record: DebateRecord) -> None:
        self._client.collection(self._collection).add(record.model_dump())

    def summarize(self) -> HistorySummary:
        from google.cloud import firestore  # noqa: PLC0415

        query = (
            self._client.collection(self._collection)
            .order_by("timestamp", direction=firestore.Query.DESCENDING)
            .limit(_RECENT_LIMIT)
        )
        records = [DebateRecord.model_validate(doc.to_dict()) for doc in query.stream()]
        return _summary_with_fallback_note(summarize_records(records, source="firestore"))


def build_history_store(settings: Settings) -> HistoryStore:
    """Build the configured history store, falling back to local on any error."""
    if settings.history_backend == "firestore" and settings.google_cloud_project:
        try:
            return FirestoreHistoryStore(settings.google_cloud_project)
        except Exception as exc:  # noqa: BLE001 - fall back to local
            logger.warning("Firestore unavailable (%s); using local history store.", exc)

    default_path = Path(__file__).resolve().parents[3] / ".data" / "history.jsonl"
    return LocalHistoryStore(default_path)
