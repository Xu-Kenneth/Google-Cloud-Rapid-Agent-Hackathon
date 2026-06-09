"""Debate history persistence (local file or Firestore)."""

from app.history.store import (
    HistoryStore,
    LocalHistoryStore,
    build_history_store,
    record_from_result,
)

__all__ = [
    "HistoryStore",
    "LocalHistoryStore",
    "build_history_store",
    "record_from_result",
]
