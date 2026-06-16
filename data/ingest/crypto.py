import asyncio
import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

_FALLBACK = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT"]


class CryptoIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str] | None = None, min_volume_usdt: float = 5_000_000, **kwargs):
        super().__init__(*args, **kwargs)
        self._static_watchlist = watchlist   # None = dynamic discovery
        self._min_volume = min_volume_usdt
        self._resolved: list[str] | None = None

    async def _get_watchlist(self) -> list[str]:
        if self._static_watchlist is not None:
            return self._static_watchlist
        if self._resolved is not None:
            return self._resolved
        try:
            loop = asyncio.get_event_loop()
            from shared.symbol_discovery import fetch_binance_symbols
            symbols = await loop.run_in_executor(
                None,
                lambda: fetch_binance_symbols(min_volume_usdt=self._min_volume),
            )
            if symbols:
                self._resolved = symbols
                self.logger.info("crypto_universe_discovered", count=len(symbols))
                return symbols
        except Exception as exc:
            self.logger.warning("crypto_discovery_failed", error=str(exc))
        self._resolved = _FALLBACK
        return _FALLBACK

    async def run_once(self):
        watchlist = await self._get_watchlist()
        rows = []
        async with httpx.AsyncClient(timeout=10) as client:
            for symbol in watchlist:
                try:
                    resp = await client.get(
                        BINANCE_KLINES_URL,
                        params={"symbol": symbol, "interval": "1m", "limit": 10},
                    )
                    resp.raise_for_status()
                    for kline in resp.json():
                        rows.append({
                            "time": datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                            "symbol": symbol,
                            "asset_class": "crypto",
                            "open": float(kline[1]),
                            "high": float(kline[2]),
                            "low": float(kline[3]),
                            "close": float(kline[4]),
                            "volume": float(kline[5]),
                        })
                except Exception as exc:
                    self.logger.warning("crypto_kline_failed", symbol=symbol, error=str(exc))
        await self.store_prices(rows)
        await self.bus.publish("data.crypto.updated", {
            "symbols": len(watchlist),
            "bar_count": len(rows),
        })
        self.logger.info("crypto_ingested", symbols=len(watchlist), bars=len(rows))
