import pandas as pd
from agents.base import AnalysisAgent
from agents.technical.indicators import rsi, macd, bollinger_bands, atr, obv

MIN_BARS = 30


class TechnicalAnalysisAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        for symbol in self.watchlist:
            rows = await self.db.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM prices
                WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
                ORDER BY time ASC
                """,
                symbol,
            )
            if len(rows) < MIN_BARS:
                continue
            await self._analyze(symbol, rows)

    async def _analyze(self, symbol: str, rows: list[dict]):
        df = pd.DataFrame(rows).set_index("time").sort_index()
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

        rsi_val = rsi(df["close"]).iloc[-1]
        m = macd(df["close"])
        macd_hist = m["histogram"].iloc[-1]
        macd_prev = m["histogram"].iloc[-2]
        bb = bollinger_bands(df["close"])
        price = df["close"].iloc[-1]
        bb_upper = bb["upper"].iloc[-1]
        bb_lower = bb["lower"].iloc[-1]
        atr_val = atr(df["high"], df["low"], df["close"]).iloc[-1]
        obv_trend = obv(df["close"], df["volume"]).diff(5).iloc[-1]

        if any(pd.isna(v) for v in [rsi_val, macd_hist, macd_prev, bb_upper, bb_lower, atr_val, obv_trend]):
            self.logger.warning("technical_nan_indicator", symbol=symbol)
            return

        signals = []

        # RSI signals
        if rsi_val < 30:
            signals.append(("oversold", 70 + (30 - rsi_val)))
        elif rsi_val > 70:
            signals.append(("overbought", 70 + (rsi_val - 70)))
        elif 45 < rsi_val < 55:
            signals.append(("neutral_rsi", 40))

        # MACD crossover (only meaningful transitions)
        if macd_hist > 0 and macd_prev <= 0:
            signals.append(("macd_bullish_cross", 75))
        elif macd_hist < 0 and macd_prev >= 0:
            signals.append(("macd_bearish_cross", 75))
        elif macd_hist > 0:
            signals.append(("macd_bullish", 55))
        elif macd_hist < 0:
            signals.append(("macd_bearish", 55))
        # else: flat MACD — no signal

        # Bollinger Band position
        bb_pct = (price - bb_lower) / (bb_upper - bb_lower) if bb_upper != bb_lower else 0.5
        if bb_pct > 0.9:
            signals.append(("bb_upper_touch", 65))
        elif bb_pct < 0.1:
            signals.append(("bb_lower_touch", 65))

        # OBV trend confirmation
        if obv_trend > 0:
            signals.append(("volume_confirms_up", 60))
        elif obv_trend < 0:
            signals.append(("volume_confirms_down", 60))

        if not signals:
            return

        signal_type = signals[0][0]
        confidence = min(100.0, float(sum(s[1] for s in signals) / len(signals)))
        reasoning = (
            f"RSI={rsi_val:.1f}, MACD_hist={macd_hist:.4f}, "
            f"BB_pct={bb_pct:.2f}, ATR={atr_val:.2f}, "
            f"signals={[s[0] for s in signals]}"
        )
        metadata = {
            "rsi": round(float(rsi_val), 2),
            "macd_hist": round(float(macd_hist), 4),
            "bb_pct": round(float(bb_pct), 3),
            "atr": round(float(atr_val), 2),
            "price": round(float(price), 2),
            "signals": [s[0] for s in signals],
        }

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=reasoning,
            metadata=metadata,
        )
        self.logger.info("technical_signal", symbol=symbol, signal=signal_type, confidence=confidence)
