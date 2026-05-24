#!/usr/bin/env python3
"""
Seed historical OHLCV data from Yahoo Finance into TimescaleDB.

Fetches daily candles for every symbol in the watchlist and inserts them
idempotently (ON CONFLICT DO NOTHING).  Run before your first backtest.

Usage:
  python scripts/seed_prices.py              # last 2 years, daily candles
  python scripts/seed_prices.py --range 5y   # last 5 years
  python scripts/seed_prices.py --symbols AAPL,MSFT --range 1y
"""
import asyncio
import argparse
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, ".")

import urllib3
import requests
import asyncpg
from shared.config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Binance-style crypto symbols → Yahoo Finance tickers
_SYMBOL_MAP = {
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
    "SOLUSDT": "SOL-USD",
    "ADAUSDT": "ADA-USD",
    "DOTUSDT": "DOT-USD",
}

# Yahoo Finance range strings accepted by the v8 chart API
_VALID_RANGES = {"1y", "2y", "5y", "max"}

# Symbols that are crypto (asset_class field)
_CRYPTO_SYMBOLS = set(_SYMBOL_MAP.keys())


def _yahoo_ticker(symbol: str) -> str:
    return _SYMBOL_MAP.get(symbol.upper(), symbol.upper())


def _asset_class(symbol: str) -> str:
    return "crypto" if symbol.upper() in _CRYPTO_SYMBOLS else "stock"


def _fetch_daily(ticker: str, range_: str) -> list[dict]:
    """Fetch daily OHLCV bars from Yahoo Finance chart API."""
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval=1d&range={range_}"
    )
    resp = requests.get(url, headers=_HEADERS, verify=False, timeout=20)
    resp.raise_for_status()
    payload = resp.json()

    result = payload.get("chart", {}).get("result")
    if not result:
        return []

    chart = result[0]
    timestamps: list[int] = chart.get("timestamp", [])
    quote = chart["indicators"]["quote"][0]
    opens   = quote.get("open",   [])
    highs   = quote.get("high",   [])
    lows    = quote.get("low",    [])
    closes  = quote.get("close",  [])
    volumes = quote.get("volume", [])

    rows = []
    for i, ts in enumerate(timestamps):
        o = opens[i]   if i < len(opens)   else None
        h = highs[i]   if i < len(highs)   else None
        l = lows[i]    if i < len(lows)    else None
        c = closes[i]  if i < len(closes)  else None
        v = volumes[i] if i < len(volumes) else None
        if None in (o, h, l, c):
            continue
        rows.append({
            "time":   datetime.fromtimestamp(ts, tz=timezone.utc),
            "open":   float(o),
            "high":   float(h),
            "low":    float(l),
            "close":  float(c),
            "volume": float(v) if v is not None else 0.0,
        })
    return rows


async def seed_symbol(
    conn: asyncpg.Connection,
    symbol: str,
    range_: str,
    dry_run: bool,
) -> int:
    ticker = _yahoo_ticker(symbol)
    asset_class = _asset_class(symbol)

    print(f"  Fetching {symbol} ({ticker}) [{range_}] ...", end=" ", flush=True)
    try:
        rows = _fetch_daily(ticker, range_)
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}")
        return 0
    except Exception as exc:
        print(f"error: {exc}")
        return 0

    if not rows:
        print("no data")
        return 0

    if dry_run:
        print(f"{len(rows)} rows (dry-run, not inserted)")
        return len(rows)

    # Bulk insert with ON CONFLICT DO NOTHING (idempotent re-runs)
    await conn.executemany(
        """
        INSERT INTO prices (time, symbol, asset_class, open, high, low, close, volume)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (time, symbol) DO NOTHING
        """,
        [
            (r["time"], symbol, asset_class, r["open"], r["high"], r["low"], r["close"], r["volume"])
            for r in rows
        ],
    )
    print(f"{len(rows)} rows inserted")
    return len(rows)


async def main(argv=None):
    parser = argparse.ArgumentParser(description="Seed historical OHLCV into TimescaleDB")
    parser.add_argument(
        "--range", default="2y", choices=list(_VALID_RANGES),
        help="Yahoo Finance range (default: 2y)",
    )
    parser.add_argument(
        "--symbols", default="",
        help="Comma-separated override list (default: all watchlist symbols)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and count rows but do not insert",
    )
    args = parser.parse_args(argv)

    if args.symbols:
        symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    else:
        symbols = (
            [s.strip() for s in settings.stock_watchlist.split(",") if s.strip()]
            + [s.strip() for s in settings.crypto_watchlist.split(",") if s.strip()]
        )

    print(f"Seeding {len(symbols)} symbols, range={args.range}")
    if args.dry_run:
        print("DRY RUN — no data will be written")

    conn = await asyncpg.connect(settings.db_dsn)
    total = 0
    for i, sym in enumerate(symbols):
        count = await seed_symbol(conn, sym, args.range, args.dry_run)
        total += count
        # Brief pause to avoid hammering Yahoo Finance
        if i < len(symbols) - 1:
            time.sleep(0.5)

    await conn.close()
    print(f"\nDone. Total rows: {total}")


if __name__ == "__main__":
    asyncio.run(main())
