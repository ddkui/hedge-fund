import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"
DEFAULT_WATCHLIST = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


class CryptoIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str] = DEFAULT_WATCHLIST, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        rows = []
        async with httpx.AsyncClient() as client:
            for symbol in self.watchlist:
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
        await self.store_prices(rows)
        await self.bus.publish("data.crypto.updated", {
            "symbols": self.watchlist,
            "bar_count": len(rows),
        })
        self.logger.info("crypto_ingested", symbols=len(self.watchlist), bars=len(rows))
