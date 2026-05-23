import pandas as pd
from agents.base import AnalysisAgent

MIN_BARS = 62
TIMEFRAMES = [5, 20, 60]
CONFIDENCE_MAP = {3: 85.0, 2: 65.0, 1: 40.0}


class MomentumQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, close FROM prices
                WHERE symbol = $1 AND time > now_or_backtest() - INTERVAL '3 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list[dict]):
        closes = pd.Series([float(r["close"]) for r in rows])
        if closes.isna().any():
            return

        momenta = []
        for n in TIMEFRAMES:
            idx = -(n + 1)
            if len(closes) > n:
                mom = (closes.iloc[-1] - closes.iloc[idx]) / closes.iloc[idx]
            else:
                mom = (closes.iloc[-1] - closes.iloc[0]) / closes.iloc[0]
            momenta.append(float(mom))

        bullish_count = sum(1 for m in momenta if m > 0)
        bearish_count = sum(1 for m in momenta if m < 0)

        if bullish_count >= 2:
            signal_type = "momentum_bullish"
            confidence = CONFIDENCE_MAP.get(bullish_count, 40.0)
        elif bearish_count >= 2:
            signal_type = "momentum_bearish"
            confidence = CONFIDENCE_MAP.get(bearish_count, 40.0)
        else:
            self.logger.debug("momentum_mixed_signal", symbol=symbol, bullish=bullish_count, bearish=bearish_count)
            return

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"mom_5={momenta[0]:.4f}, mom_20={momenta[1]:.4f}, mom_60={momenta[2]:.4f}",
            metadata={
                "mom_5": round(momenta[0], 4),
                "mom_20": round(momenta[1], 4),
                "mom_60": round(momenta[2], 4),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
            },
        )
        self.logger.info("momentum_signal", symbol=symbol, signal=signal_type, confidence=confidence)
