# gateway/routers/prices.py
"""
OHLCV price endpoint.

- Regular symbols (AAPL, BTCUSDT, etc.) → Yahoo Finance chart API
- Hyperliquid symbols (HL:BTC, HL:ETH, HL:HYPE, etc.) → Hyperliquid info API

yfinance's auth wrapper is broken on Windows due to Yahoo's consent changes;
hitting the chart endpoint directly with browser headers is reliable.
"""
import asyncio
import time as _time
from functools import partial
import urllib3
import requests
from fastapi import APIRouter, HTTPException

router = APIRouter()

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Map common dashboard symbols → Yahoo Finance tickers
_YAHOO_MAP = {
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
    "SOLUSDT": "SOL-USD",
}

_VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d"}
_VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y"}

_HL_INTERVAL_MAP = {
    "5m": "5m", "15m": "15m", "30m": "30m",
    "1h": "1h", "1d": "1d",
}
_HL_PERIOD_SECONDS = {
    "1d": 86_400, "5d": 5 * 86_400, "1mo": 30 * 86_400,
    "3mo": 90 * 86_400, "6mo": 180 * 86_400, "1y": 365 * 86_400,
}
_HL_API = "https://api.hyperliquid.xyz/info"


# ---------------------------------------------------------------------------
# Yahoo Finance fetch
# ---------------------------------------------------------------------------

def _fetch_yahoo(ticker: str, period: str, interval: str) -> list[dict]:
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?interval={interval}&range={period}"
    )
    resp = requests.get(url, headers=_HEADERS, verify=False, timeout=15)
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

    candles = []
    for i, ts in enumerate(timestamps):
        o = opens[i] if i < len(opens) else None
        h = highs[i] if i < len(highs) else None
        l = lows[i] if i < len(lows) else None
        c = closes[i] if i < len(closes) else None
        if None in (o, h, l, c):
            continue
        candles.append({
            "time":   int(ts),
            "open":   round(float(o), 4),
            "high":   round(float(h), 4),
            "low":    round(float(l), 4),
            "close":  round(float(c), 4),
            "volume": round(float(volumes[i]), 2) if i < len(volumes) and volumes[i] else 0,
        })
    return candles


# ---------------------------------------------------------------------------
# Hyperliquid fetch
# ---------------------------------------------------------------------------

def _fetch_hyperliquid(coin: str, period: str, interval: str) -> list[dict]:
    hl_interval = _HL_INTERVAL_MAP.get(interval, "1h")
    duration = _HL_PERIOD_SECONDS.get(period, 5 * 86_400)
    end_ms = int(_time.time() * 1000)
    start_ms = end_ms - duration * 1000

    payload = {
        "type": "candleSnapshot",
        "req": {
            "coin": coin.upper(),
            "interval": hl_interval,
            "startTime": start_ms,
            "endTime": end_ms,
        },
    }
    resp = requests.post(_HL_API, json=payload, timeout=15)
    resp.raise_for_status()
    raw = resp.json()

    candles = []
    for bar in raw:
        t = bar.get("t")  # open time in ms
        if t is None:
            continue
        candles.append({
            "time":   int(t) // 1000,          # seconds for lightweight-charts
            "open":   round(float(bar["o"]), 4),
            "high":   round(float(bar["h"]), 4),
            "low":    round(float(bar["l"]), 4),
            "close":  round(float(bar["c"]), 4),
            "volume": round(float(bar.get("v", 0)), 4),
        })
    return candles


# ---------------------------------------------------------------------------
# Symbol search & universe discovery
# ---------------------------------------------------------------------------

@router.get("/search")
async def search_symbols(q: str = "", limit: int = 20):
    """
    Search any tradable instrument globally (stocks, ETFs, futures, forex, crypto).
    Backed by Yahoo Finance search — covers every exchange.
    Also prepends matching Hyperliquid perps for HL: queries.
    """
    if not q:
        return []

    loop = asyncio.get_event_loop()

    # Run Yahoo search in executor (blocking requests call)
    from shared.symbol_discovery import search_yahoo, fetch_hyperliquid_symbols
    results = await loop.run_in_executor(None, lambda: search_yahoo(q, limit))

    # Prepend HL: results if query looks like a crypto coin name
    if len(q) >= 2:
        try:
            hl_syms = await loop.run_in_executor(None, fetch_hyperliquid_symbols)
            q_upper = q.upper()
            hl_matches = [
                {"symbol": s, "name": f"{s[3:]} Perpetual", "exchange": "Hyperliquid", "type": "Perpetual"}
                for s in hl_syms
                if q_upper in s[3:]  # "HL:BTC" → match on "BTC"
            ]
            results = hl_matches + results
        except Exception:
            pass

    return results[:limit]


@router.get("/universe/crypto")
async def crypto_universe(min_volume: float = 1_000_000):
    """All actively traded Binance USDT pairs above min 24 h volume."""
    from shared.symbol_discovery import fetch_binance_symbols
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(
        None, lambda: fetch_binance_symbols(min_volume_usdt=min_volume)
    )
    return {"count": len(symbols), "symbols": symbols}


@router.get("/universe/hyperliquid")
async def hyperliquid_universe():
    """All perpetual markets currently listed on Hyperliquid."""
    from shared.symbol_discovery import fetch_hyperliquid_symbols
    loop = asyncio.get_event_loop()
    symbols = await loop.run_in_executor(None, fetch_hyperliquid_symbols)
    return {"count": len(symbols), "symbols": symbols}


# ---------------------------------------------------------------------------
# OHLCV candles
# ---------------------------------------------------------------------------

@router.get("/{symbol}")
async def get_prices(symbol: str, period: str = "5d", interval: str = "1h"):
    if interval not in _VALID_INTERVALS:
        raise HTTPException(400, f"interval must be one of {_VALID_INTERVALS}")
    if period not in _VALID_PERIODS:
        raise HTTPException(400, f"period must be one of {_VALID_PERIODS}")

    sym = symbol.upper()
    loop = asyncio.get_event_loop()

    try:
        if sym.startswith("HL:"):
            coin = sym[3:]  # "HL:BTC" → "BTC"
            candles = await loop.run_in_executor(
                None, partial(_fetch_hyperliquid, coin, period, interval)
            )
        else:
            ticker = _YAHOO_MAP.get(sym, sym)
            candles = await loop.run_in_executor(
                None, partial(_fetch_yahoo, ticker, period, interval)
            )
    except requests.HTTPError as exc:
        raise HTTPException(502, f"Price source error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(502, f"Price fetch error: {exc}") from exc

    if not candles:
        raise HTTPException(404, f"No data found for {symbol}")
    return candles
