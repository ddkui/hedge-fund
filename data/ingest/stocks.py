import asyncio
import yfinance as yf
from datetime import timezone
from data.ingest.base import DataIngestAgent

DEFAULT_WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "SPY", "QQQ"]


class StocksIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str] = DEFAULT_WATCHLIST, **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    def _fetch_ticker_history(self, symbol: str):
        return yf.Ticker(symbol).history(period="1d", interval="1m")

    async def run_once(self):
        rows = []
        loop = asyncio.get_event_loop()
        for symbol in self.watchlist:
            hist = await loop.run_in_executor(None, self._fetch_ticker_history, symbol)
            for ts, row in hist.iterrows():
                rows.append({
                    "time": ts.to_pydatetime().replace(tzinfo=timezone.utc),
                    "symbol": symbol,
                    "asset_class": "stock",
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                })
        await self.store_prices(rows)
        await self.bus.publish("data.stocks.updated", {
            "symbols": self.watchlist,
            "bar_count": len(rows),
        })
        self.logger.info("stocks_ingested", symbols=len(self.watchlist), bars=len(rows))
