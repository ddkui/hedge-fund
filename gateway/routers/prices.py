# gateway/routers/prices.py
"""
OHLCV price endpoint — fetches from Yahoo Finance chart API directly.
yfinance's auth wrapper is broken on Windows due to Yahoo's consent changes;
hitting the chart endpoint directly with browser headers is reliable.
"""
import asyncio
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

# Map dashboard watchlist symbols → Yahoo Finance tickers
_SYMBOL_MAP = {
    "BTCUSDT": "BTC-USD",
    "ETHUSDT": "ETH-USD",
    "BNBUSDT": "BNB-USD",
    "SOLUSDT": "SOL-USD",
}

_VALID_INTERVALS = {"1m", "5m", "15m", "30m", "1h", "1d"}
_VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y"}


def _fetch_ohlcv(ticker: str, period: str, interval: str) -> list[dict]:
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
            continue  # skip incomplete bars (market still open)
        candles.append({
            "time":   int(ts),
            "open":   round(float(o), 4),
            "high":   round(float(h), 4),
            "low":    round(float(l), 4),
            "close":  round(float(c), 4),
            "volume": round(float(volumes[i]), 2) if i < len(volumes) and volumes[i] else 0,
        })
    return candles


@router.get("/{symbol}")
async def get_prices(symbol: str, period: str = "5d", interval: str = "1h"):
    if interval not in _VALID_INTERVALS:
        raise HTTPException(400, f"interval must be one of {_VALID_INTERVALS}")
    if period not in _VALID_PERIODS:
        raise HTTPException(400, f"period must be one of {_VALID_PERIODS}")

    ticker = _SYMBOL_MAP.get(symbol.upper(), symbol.upper())
    loop = asyncio.get_event_loop()
    try:
        candles = await loop.run_in_executor(None, partial(_fetch_ohlcv, ticker, period, interval))
    except requests.HTTPError as exc:
        raise HTTPException(502, f"Yahoo Finance error: {exc}") from exc
    except Exception as exc:
        raise HTTPException(502, f"Price fetch error: {exc}") from exc

    if not candles:
        raise HTTPException(404, f"No data found for {symbol}")
    return candles
