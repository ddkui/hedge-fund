# agents/quant/vwap/agent.py
from datetime import datetime, timezone, timedelta
from agents.base import AnalysisAgent
from shared.agent_params import load_agent_params

DEFAULTS = {
    "deviation_threshold_pct": 1.5,
    "min_candles": 5,
    "crypto_window_hours": 24,
}

CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}


def _compute_vwap(candles: list[dict]) -> float:
    total_vol = sum(float(c["volume"]) for c in candles)
    if total_vol == 0:
        return float(candles[0]["close"])
    return sum(float(c["close"]) * float(c["volume"]) for c in candles) / total_vol


class VWAPDeviationAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        regime_data = await self.bus.get("macro:current_regime") or {}
        regime = regime_data.get("regime", "expansion")
        for symbol in self.watchlist:
            asset_class = "crypto" if symbol in CRYPTO_SYMBOLS else "stock"
            await self._analyze(symbol, asset_class, regime)

    async def _analyze(self, symbol: str, asset_class: str, regime: str):
        params = load_agent_params("vwap", regime, DEFAULTS)
        threshold = float(params["deviation_threshold_pct"])
        min_candles = int(params["min_candles"])
        crypto_hours = int(params["crypto_window_hours"])

        now = datetime.now(timezone.utc)
        if asset_class == "crypto":
            window_start = now - timedelta(hours=crypto_hours)
        else:
            today = now.date()
            market_open = datetime(today.year, today.month, today.day, 14, 30, tzinfo=timezone.utc)
            window_start = market_open if now >= market_open else (market_open - timedelta(days=1))

        candles = await self.db.fetch(
            "SELECT close, volume, time FROM prices WHERE symbol = $1 AND time >= $2 ORDER BY time ASC",
            symbol, window_start,
        )

        if len(candles) < min_candles:
            return

        vwap = _compute_vwap(candles)
        current_close = float(candles[-1]["close"])
        if vwap == 0:
            return

        deviation_pct = (current_close - vwap) / vwap * 100

        if deviation_pct < -threshold:
            signal_type = "bullish_signal"
        elif deviation_pct > threshold:
            signal_type = "bearish_signal"
        else:
            return

        confidence = min(80.0, abs(deviation_pct) * 15)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=round(confidence, 2),
            reasoning=(
                f"VWAP={vwap:.4f}, current={current_close:.4f}, "
                f"deviation={deviation_pct:+.2f}% "
                f"({'below' if deviation_pct < 0 else 'above'} {threshold}% threshold), regime={regime}"
            ),
            metadata={
                "vwap": round(vwap, 6),
                "current_close": current_close,
                "deviation_pct": round(deviation_pct, 4),
                "candle_count": len(candles),
                "regime": regime,
            },
        )
        self.logger.info("vwap_signal", symbol=symbol, signal=signal_type,
                         deviation=round(deviation_pct, 2))
