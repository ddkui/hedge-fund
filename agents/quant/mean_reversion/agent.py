import pandas as pd
from agents.base import AnalysisAgent
from agents.technical.indicators import rsi

MIN_BARS = 30
ZSCORE_THRESHOLD = 2.0


class MeanReversionQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, close FROM prices
                WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list[dict]):
        closes = pd.Series([float(r["close"]) for r in rows])

        rolling_mean = closes.rolling(20).mean()
        rolling_std = closes.rolling(20).std()

        last_mean = rolling_mean.iloc[-1]
        last_std = rolling_std.iloc[-1]

        if pd.isna(last_mean) or pd.isna(last_std) or last_std == 0:
            return

        zscore = float((closes.iloc[-1] - last_mean) / last_std)
        rsi_val = rsi(closes).iloc[-1]

        if pd.isna(rsi_val):
            return

        if zscore > ZSCORE_THRESHOLD and rsi_val > 65:
            signal_type = "reversion_bearish"
        elif zscore < -ZSCORE_THRESHOLD and rsi_val < 35:
            signal_type = "reversion_bullish"
        else:
            return

        confidence = min(100.0, abs(zscore) * 35)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"zscore={zscore:.2f}, rsi={rsi_val:.1f}, mean={last_mean:.2f}",
            metadata={
                "zscore": round(zscore, 3),
                "rsi": round(float(rsi_val), 1),
                "rolling_mean": round(float(last_mean), 2),
            },
        )
        self.logger.info("mean_reversion_signal", symbol=symbol, zscore=zscore, rsi=rsi_val)
