"""Market data tool: turn a ticker into a structured, citable evidence pack.

The agents argue strictly from the evidence returned here, so this module owns all
external data access and normalizes two providers into one shape:

* **Finnhub** (preferred when ``FINNHUB_API_KEY`` is set) via its REST API.
* **yfinance** fallback, which needs no key.

If both fail we return a ``limited`` pack rather than raising, so a debate can still
proceed with an explicit caveat.
"""

from __future__ import annotations

import datetime as dt
import logging

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

FINNHUB_BASE = "https://finnhub.io/api/v1"
_HTTP_TIMEOUT = 10.0
_MAX_NEWS = 5


# --------------------------------------------------------------------------- #
# Shapes
# --------------------------------------------------------------------------- #
class Quote(BaseModel):
    price: float | None = None
    change: float | None = None
    percent_change: float | None = None
    currency: str = "USD"


class Fundamentals(BaseModel):
    market_cap: float | None = None
    pe_ratio: float | None = None
    eps: float | None = None
    high_52w: float | None = None
    low_52w: float | None = None
    beta: float | None = None


class NewsItem(BaseModel):
    headline: str
    source: str | None = None
    url: str | None = None
    published: str | None = None  # ISO date string


class EvidencePack(BaseModel):
    """Everything the agents are allowed to cite for one ticker."""

    ticker: str
    company_name: str | None = None
    quote: Quote = Field(default_factory=Quote)
    fundamentals: Fundamentals = Field(default_factory=Fundamentals)
    news: list[NewsItem] = Field(default_factory=list)
    source: str = "limited"  # "finnhub" | "yfinance" | "limited"
    notes: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return self.quote.price is None and not self.news

    def citable_items(self) -> list[dict[str, str]]:
        """Flatten the pack into enumerated, citable items (E1, E2, ...)."""
        items: list[dict[str, str]] = []

        def add(text: str) -> None:
            items.append({"id": f"E{len(items) + 1}", "text": text})

        q, f = self.quote, self.fundamentals
        if q.price is not None:
            chg = (
                f" ({q.percent_change:+.2f}%)" if q.percent_change is not None else ""
            )
            add(f"Latest price: {q.price} {q.currency}{chg}")
        if f.market_cap is not None:
            add(f"Market cap: {f.market_cap}")
        if f.pe_ratio is not None:
            add(f"P/E ratio: {f.pe_ratio}")
        if f.eps is not None:
            add(f"EPS: {f.eps}")
        if f.high_52w is not None and f.low_52w is not None:
            add(f"52-week range: {f.low_52w} - {f.high_52w}")
        if f.beta is not None:
            add(f"Beta: {f.beta}")
        for n in self.news:
            src = f" [{n.source}]" if n.source else ""
            add(f"News: {n.headline}{src}")
        return items

    def as_prompt_block(self) -> str:
        """Human-readable evidence block injected into agent prompts."""
        lines = [f"Company: {self.company_name or self.ticker} ({self.ticker})"]
        lines += [f"- {it['id']}: {it['text']}" for it in self.citable_items()]
        if self.notes:
            lines.append("Notes: " + "; ".join(self.notes))
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Finnhub provider
# --------------------------------------------------------------------------- #
def _from_finnhub(ticker: str, api_key: str, client: httpx.Client) -> EvidencePack:
    params = {"symbol": ticker, "token": api_key}

    quote_raw = client.get(f"{FINNHUB_BASE}/quote", params=params).json()
    profile = client.get(f"{FINNHUB_BASE}/stock/profile2", params=params).json()
    metric = (
        client.get(
            f"{FINNHUB_BASE}/stock/metric",
            params={**params, "metric": "all"},
        )
        .json()
        .get("metric", {})
    )

    today = dt.date.today()
    news_raw = client.get(
        f"{FINNHUB_BASE}/company-news",
        params={
            **params,
            "from": (today - dt.timedelta(days=14)).isoformat(),
            "to": today.isoformat(),
        },
    ).json()

    if not quote_raw or quote_raw.get("c") in (None, 0):
        raise ValueError(f"Finnhub returned no quote for {ticker}")

    news = [
        NewsItem(
            headline=n.get("headline", ""),
            source=n.get("source"),
            url=n.get("url"),
            published=(
                dt.datetime.fromtimestamp(n["datetime"], tz=dt.timezone.utc)
                .date()
                .isoformat()
                if n.get("datetime")
                else None
            ),
        )
        for n in (news_raw or [])[:_MAX_NEWS]
        if n.get("headline")
    ]

    return EvidencePack(
        ticker=ticker,
        company_name=profile.get("name") or ticker,
        quote=Quote(
            price=quote_raw.get("c"),
            change=quote_raw.get("d"),
            percent_change=quote_raw.get("dp"),
            currency=profile.get("currency", "USD"),
        ),
        fundamentals=Fundamentals(
            market_cap=profile.get("marketCapitalization"),
            pe_ratio=metric.get("peTTM"),
            eps=metric.get("epsTTM"),
            high_52w=metric.get("52WeekHigh"),
            low_52w=metric.get("52WeekLow"),
            beta=metric.get("beta"),
        ),
        news=news,
        source="finnhub",
    )


# --------------------------------------------------------------------------- #
# yfinance provider
# --------------------------------------------------------------------------- #
def _from_yfinance(ticker: str) -> EvidencePack:
    import yfinance as yf  # imported lazily; heavy and only needed on fallback

    tk = yf.Ticker(ticker)
    info = dict(tk.info or {})
    if not info or info.get("currentPrice") is None and info.get("regularMarketPrice") is None:
        raise ValueError(f"yfinance returned no data for {ticker}")

    price = info.get("currentPrice") or info.get("regularMarketPrice")
    prev = info.get("regularMarketPreviousClose")
    change = (price - prev) if (price is not None and prev) else None
    pct = (change / prev * 100) if (change is not None and prev) else None

    news_items: list[NewsItem] = []
    for n in (getattr(tk, "news", None) or [])[:_MAX_NEWS]:
        content = n.get("content", n)  # yfinance shape varies by version
        title = content.get("title") or n.get("title")
        if not title:
            continue
        news_items.append(
            NewsItem(
                headline=title,
                source=(content.get("provider") or {}).get("displayName")
                if isinstance(content.get("provider"), dict)
                else n.get("publisher"),
                url=(content.get("canonicalUrl") or {}).get("url")
                if isinstance(content.get("canonicalUrl"), dict)
                else n.get("link"),
            )
        )

    return EvidencePack(
        ticker=ticker,
        company_name=info.get("longName") or info.get("shortName") or ticker,
        quote=Quote(
            price=price,
            change=change,
            percent_change=pct,
            currency=info.get("currency", "USD"),
        ),
        fundamentals=Fundamentals(
            market_cap=info.get("marketCap"),
            pe_ratio=info.get("trailingPE"),
            eps=info.get("trailingEps"),
            high_52w=info.get("fiftyTwoWeekHigh"),
            low_52w=info.get("fiftyTwoWeekLow"),
            beta=info.get("beta"),
        ),
        news=news_items,
        source="yfinance",
    )


# --------------------------------------------------------------------------- #
# Public entrypoint
# --------------------------------------------------------------------------- #
def fetch_evidence(
    ticker: str,
    *,
    finnhub_api_key: str = "",
    client: httpx.Client | None = None,
) -> EvidencePack:
    """Fetch an evidence pack for ``ticker``, trying Finnhub then yfinance.

    Never raises for data-availability problems: returns a ``limited`` pack with a
    note so the debate can proceed with an explicit caveat.
    """
    ticker = ticker.strip().upper()
    errors: list[str] = []

    if finnhub_api_key:
        owns_client = client is None
        client = client or httpx.Client(timeout=_HTTP_TIMEOUT)
        try:
            return _from_finnhub(ticker, finnhub_api_key, client)
        except Exception as exc:  # noqa: BLE001 - degrade gracefully
            logger.warning("Finnhub fetch failed for %s: %s", ticker, exc)
            errors.append(f"finnhub: {exc}")
        finally:
            if owns_client:
                client.close()

    try:
        return _from_yfinance(ticker)
    except Exception as exc:  # noqa: BLE001 - degrade gracefully
        logger.warning("yfinance fetch failed for %s: %s", ticker, exc)
        errors.append(f"yfinance: {exc}")

    return EvidencePack(
        ticker=ticker,
        company_name=ticker,
        source="limited",
        notes=["Live market data unavailable; debate proceeds on limited data."]
        + errors,
    )
