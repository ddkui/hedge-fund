# agents/quant/news_momentum/agent.py
from agents.base import AnalysisAgent
from shared.agent_params import load_agent_params

DEFAULTS = {
    "sentiment_weight": 0.40,
    "momentum_weight": 0.60,
    "momentum_lookback": 20,
    "composite_threshold": 1.0,
    "sentiment_lookback_hours": 2,
}


class NewsMomentumAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        regime_data = await self.bus.get("macro:current_regime") or {}
        regime = regime_data.get("regime", "expansion")
        for symbol in self.watchlist:
            await self._analyze(symbol, regime)

    async def _analyze(self, symbol: str, regime: str):
        params = load_agent_params("news_momentum", regime, DEFAULTS)
        lookback = int(params["momentum_lookback"])
        sent_hours = int(params["sentiment_lookback_hours"])
        threshold = float(params["composite_threshold"])
        sent_w = float(params["sentiment_weight"])
        mom_w = float(params["momentum_weight"])

        sentiment_row = await self.db.fetchrow(
            """
            SELECT signal_type, confidence FROM signals
            WHERE agent = 'sentiment' AND symbol = $1
              AND time > now_or_backtest() - INTERVAL '1 hour' * $2
            ORDER BY time DESC LIMIT 1
            """,
            symbol, sent_hours,
        )
        if sentiment_row is None:
            return

        price_rows = await self.db.fetch(
            "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT $2",
            symbol, lookback,
        )
        if len(price_rows) < 2:
            return

        latest_close = float(price_rows[0]["close"])
        oldest_close = float(price_rows[-1]["close"])
        if oldest_close == 0:
            return
        price_momentum_pct = (latest_close - oldest_close) / oldest_close * 100

        sig = sentiment_row["signal_type"]
        conf = float(sentiment_row["confidence"])
        if "bullish" in sig:
            sentiment_score = +conf
        elif "bearish" in sig:
            sentiment_score = -conf
        else:
            sentiment_score = 0.0

        sentiment_dir = 1 if sentiment_score > 0 else (-1 if sentiment_score < 0 else 0)
        momentum_dir = 1 if price_momentum_pct > 0 else (-1 if price_momentum_pct < 0 else 0)
        if sentiment_dir != 0 and momentum_dir != 0 and sentiment_dir != momentum_dir:
            return

        composite = (sentiment_score * sent_w) + (price_momentum_pct * mom_w)

        if composite > threshold:
            signal_type = "bullish_signal"
        elif composite < -threshold:
            signal_type = "bearish_signal"
        else:
            return

        confidence = min(85.0, max(0.0, abs(composite) * 8))

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=round(confidence, 2),
            reasoning=(
                f"News-momentum composite={composite:.2f} (sent={sentiment_score:.1f}x{sent_w}, "
                f"mom={price_momentum_pct:.2f}%x{mom_w}) regime={regime}"
            ),
            metadata={
                "sentiment_score": sentiment_score,
                "price_momentum_pct": round(price_momentum_pct, 4),
                "composite": round(composite, 4),
                "regime": regime,
            },
        )
        self.logger.info("news_momentum_signal", symbol=symbol,
                         signal=signal_type, composite=round(composite, 2))
