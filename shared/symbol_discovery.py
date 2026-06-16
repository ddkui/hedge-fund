# shared/symbol_discovery.py
"""
Dynamic symbol discovery from live exchange APIs.

Fetch the full tradable universe without maintaining static lists.
Each function returns symbols in the format used by this system's prices endpoint.
"""
import requests
import warnings

_TIMEOUT = 15


# ── Crypto: Binance ──────────────────────────────────────────────────────────

def fetch_binance_symbols(
    quote_asset: str = "USDT",
    min_volume_usdt: float = 1_000_000,
) -> list[str]:
    """
    Return all actively traded Binance spot pairs quoted in `quote_asset`.
    Filters to symbols with 24 h volume >= min_volume_usdt to avoid micro-caps.
    """
    try:
        info = requests.get(
            "https://api.binance.com/api/v3/exchangeInfo", timeout=_TIMEOUT
        ).json()
        active = {
            s["symbol"]
            for s in info.get("symbols", [])
            if s["status"] == "TRADING" and s["quoteAsset"] == quote_asset
        }
    except Exception as exc:
        warnings.warn(f"symbol_discovery: Binance exchangeInfo failed: {exc}")
        return []

    if not active:
        return []

    try:
        tickers = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr", timeout=_TIMEOUT
        ).json()
        result = []
        for t in tickers:
            sym = t.get("symbol", "")
            if sym not in active:
                continue
            try:
                vol = float(t.get("quoteVolume", 0))
            except (TypeError, ValueError):
                vol = 0.0
            if vol >= min_volume_usdt:
                result.append(sym)
        result.sort()
        return result
    except Exception as exc:
        warnings.warn(f"symbol_discovery: Binance 24hr ticker failed: {exc}")
        return list(active)


# ── Perps: Hyperliquid ───────────────────────────────────────────────────────

def fetch_hyperliquid_symbols() -> list[str]:
    """
    Return all perpetual markets on Hyperliquid, prefixed with 'HL:'.
    """
    try:
        resp = requests.post(
            "https://api.hyperliquid.xyz/info",
            json={"type": "meta"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        coins = [asset["name"] for asset in data.get("universe", [])]
        return [f"HL:{c}" for c in sorted(coins)]
    except Exception as exc:
        warnings.warn(f"symbol_discovery: Hyperliquid meta failed: {exc}")
        return []


# ── Equities: Alpaca ─────────────────────────────────────────────────────────

def fetch_alpaca_symbols(api_key: str, secret_key: str, paper: bool = True) -> list[str]:
    """
    Return all actively tradable US equities and ETFs from Alpaca.
    Requires valid Alpaca credentials.
    """
    base = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
    headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": secret_key}
    try:
        resp = requests.get(
            f"{base}/v2/assets",
            headers=headers,
            params={"status": "active", "asset_class": "us_equity"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        symbols = sorted(
            a["symbol"] for a in resp.json() if a.get("tradable") and a.get("symbol")
        )
        return symbols
    except Exception as exc:
        warnings.warn(f"symbol_discovery: Alpaca assets failed: {exc}")
        return []


# ── Yahoo Finance symbol search ───────────────────────────────────────────────

_YF_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def search_yahoo(query: str, limit: int = 20) -> list[dict]:
    """
    Search Yahoo Finance for any tradable instrument globally.
    Returns list of {symbol, name, exchange, type} dicts.
    Covers stocks, ETFs, futures, forex, crypto, indices — all exchanges.
    """
    if not query or not query.strip():
        return []
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={
                "q": query.strip(),
                "lang": "en-US",
                "quotesCount": limit,
                "newsCount": 0,
                "enableFuzzyQuery": True,
                "enableNavLinks": False,
            },
            headers=_YF_HEADERS,
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = []
        for q in resp.json().get("quotes", []):
            sym = q.get("symbol")
            if not sym:
                continue
            results.append({
                "symbol": sym,
                "name": q.get("longname") or q.get("shortname") or sym,
                "exchange": q.get("exchange", ""),
                "type": q.get("typeDisp") or q.get("quoteType", ""),
            })
        return results
    except Exception as exc:
        warnings.warn(f"symbol_discovery: Yahoo search failed: {exc}")
        return []
