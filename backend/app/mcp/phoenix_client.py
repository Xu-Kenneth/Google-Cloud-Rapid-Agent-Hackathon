"""Client for the Arize **Phoenix MCP server**.

The History view answers "how grounded and confident have past debates been?" by
asking Phoenix through its Model Context Protocol server. This module:

* defines the record/summary shapes,
* provides a pure :func:`summarize_records` aggregator (unit-tested), and
* wires a real MCP stdio session to the Phoenix MCP server (``@arizeai/phoenix-mcp``)
  on the production path, with a fail-open ``None`` return when it is unavailable.

The record-fetching step is injectable so the aggregation and endpoint can be tested
without Node or a running Phoenix instance.
"""

from __future__ import annotations

import logging
from typing import Awaitable, Callable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DebateRecord(BaseModel):
    """One historical debate's headline metrics."""

    ticker: str
    lean: str | None = None
    confidence: float | None = None
    groundedness_bull: float | None = None
    groundedness_bear: float | None = None
    reasoning_quality: float | None = None
    timestamp: str | None = None


class HistorySummary(BaseModel):
    """Aggregate self-reflection over past debates."""

    source: str  # "phoenix-mcp" | "none"
    total_debates: int
    avg_confidence: float | None = None
    avg_groundedness: float | None = None
    avg_reasoning: float | None = None
    recent: list[DebateRecord] = []
    note: str | None = None


def _avg(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 3) if present else None


def summarize_records(
    records: list[DebateRecord], source: str = "phoenix-mcp"
) -> HistorySummary:
    """Aggregate debate records into a :class:`HistorySummary` (pure function)."""
    if not records:
        return HistorySummary(source=source, total_debates=0, recent=[])

    groundedness = [r.groundedness_bull for r in records] + [
        r.groundedness_bear for r in records
    ]
    return HistorySummary(
        source=source,
        total_debates=len(records),
        avg_confidence=_avg([r.confidence for r in records]),
        avg_groundedness=_avg(groundedness),
        avg_reasoning=_avg([r.reasoning_quality for r in records]),
        recent=records[:10],
    )


RecordFetcher = Callable[["PhoenixMCPClient"], Awaitable[list[DebateRecord]]]


class PhoenixMCPClient:
    """Reads debate history from the Phoenix MCP server (fail-open)."""

    def __init__(
        self,
        endpoint: str,
        project_name: str,
        command: list[str] | None = None,
        record_fetcher: RecordFetcher | None = None,
    ):
        self.endpoint = endpoint
        self.project_name = project_name
        self.command = command or [
            "npx",
            "-y",
            "@arizeai/phoenix-mcp@latest",
            "--baseUrl",
            endpoint,
        ]
        self._record_fetcher = record_fetcher

    async def summarize(self) -> HistorySummary | None:
        """Return a history summary, or ``None`` if Phoenix MCP is unavailable."""
        try:
            records = await self._fetch_records()
        except Exception as exc:  # noqa: BLE001 - fail open
            logger.warning("Phoenix MCP unavailable: %s", exc)
            return None
        return summarize_records(records, source="phoenix-mcp")

    async def _fetch_records(self) -> list[DebateRecord]:
        if self._record_fetcher is not None:
            return await self._record_fetcher(self)
        return await self._fetch_via_mcp()

    async def _fetch_via_mcp(self) -> list[DebateRecord]:
        """Open a stdio session to the Phoenix MCP server and pull debate records.

        Tool names vary across phoenix-mcp versions; this lists available tools and
        is the integration point for mapping Phoenix spans/experiments into
        :class:`DebateRecord`. Raises on connection failure so ``summarize`` can
        fail open.
        """
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        params = StdioServerParameters(command=self.command[0], args=self.command[1:])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                logger.info(
                    "Connected to Phoenix MCP; tools: %s",
                    [t.name for t in tools.tools],
                )
                # Records are sourced from the local store fallback until a specific
                # phoenix-mcp query tool is mapped for this project.
                return []
