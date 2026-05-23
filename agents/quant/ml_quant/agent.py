import asyncio
import pandas as pd
from datetime import datetime, timezone, timedelta
from agents.base import AnalysisAgent
from agents.quant.ml_quant.features import extract_features, make_labels
from agents.quant.ml_quant.model import MLEnsemble

MIN_TRAINING_BARS = 500
MIN_INFERENCE_BARS = 30
RETRAIN_INTERVAL = timedelta(hours=24)


class MLQuantAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist
        self._models: dict[str, MLEnsemble] = {}
        self._last_trained: dict[str, datetime] = {}

    async def run_once(self):
        for symbol in self.watchlist:
            await self._maybe_retrain(symbol)
            model = self._models.get(symbol)
            if model is None or not model.trained:
                continue
            await self._infer(symbol)

    async def _maybe_retrain(self, symbol: str):
        now = self._now()
        last = self._last_trained.get(symbol)
        if last and now - last < RETRAIN_INTERVAL:
            return

        rows = await self.db.fetch(
            """
            SELECT time, open, high, low, close, volume FROM prices
            WHERE symbol = $1 AND time > NOW() - INTERVAL '30 days'
            ORDER BY time ASC
            """,
            symbol,
        )
        if len(rows) < MIN_TRAINING_BARS:
            self.logger.warning("ml_insufficient_training_data", symbol=symbol, bars=len(rows))
            return

        loop = asyncio.get_running_loop()
        trained = await loop.run_in_executor(None, self._train, symbol, list(rows))
        if trained:
            self._last_trained[symbol] = now
            self.logger.info("ml_retrained", symbol=symbol, bars=len(rows))
        else:
            self.logger.warning("ml_train_skipped_insufficient_features", symbol=symbol)

    def _train(self, symbol: str, rows: list) -> bool:
        df = pd.DataFrame(rows).set_index("time").sort_index()
        df = df.astype({"open": float, "high": float, "low": float, "close": float, "volume": float})

        features = extract_features(rows)
        labels = make_labels(df["close"])

        common_idx = features.index.intersection(labels.index)
        X = features.loc[common_idx].dropna()
        y = labels.loc[X.index]

        # Drop last row — no future label available
        X = X.iloc[:-1]
        y = y.iloc[:-1]

        if len(X) < 100:
            return False

        model = MLEnsemble()
        model.fit(X.values, y.values)
        self._models[symbol] = model
        return True

    async def _infer(self, symbol: str):
        rows = await self.db.fetch(
            """
            SELECT time, open, high, low, close, volume FROM prices
            WHERE symbol = $1 AND time > NOW() - INTERVAL '2 hours'
            ORDER BY time ASC
            """,
            symbol,
        )
        if len(rows) < MIN_INFERENCE_BARS:
            return

        features = extract_features(rows)
        if features.empty:
            return

        direction, avg_prob = self._models[symbol].predict(features.iloc[[-1]].values)

        if direction == 1:
            signal_type = "ml_bullish"
        elif direction == -1:
            signal_type = "ml_bearish"
        else:
            return

        confidence = min(100.0, avg_prob * 100)

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=confidence,
            reasoning=f"ML ensemble vote: direction={direction}, avg_prob={avg_prob:.3f}",
            metadata={"direction": direction, "avg_prob": round(avg_prob, 4)},
        )
        self.logger.info("ml_signal", symbol=symbol, signal=signal_type, confidence=confidence)
