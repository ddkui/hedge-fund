"""
KronosResearchAgent — uses the Kronos foundation model (AAAI 2026)
to forecast OHLCV price movements for all watchlist symbols.

Runs every 6 hours. Outputs:
  - Row per symbol in kronos_forecasts table
  - signal per symbol via store_signal() (feeds into aggregator)
  - Full research report published to Redis research.kronos channel
  - Obsidian markdown report in memory/obsidian/kronos/
"""
import sys
import asyncio
from pathlib import Path
from datetime import datetime, timezone

import pandas as pd

# Kronos model source lives in models/kronos_src/ (downloaded by setup_kronos.py)
_KRONOS_SRC = Path(__file__).parents[3] / "models" / "kronos_src"
sys.path.insert(0, str(_KRONOS_SRC))

from agents.base import AnalysisAgent
from shared.memory import MemoryMixin
from shared.config import settings

PRED_LEN = 24        # candles to forecast ahead
LOOKBACK = 400       # max history candles fed to model (mini supports 2048)
MIN_CANDLES = 50     # skip symbol if fewer rows in DB
MODEL_ID = "NeoQuasar/Kronos-mini"
TOKENIZER_ID = "NeoQuasar/Kronos-Tokenizer-2k"


def _watchlist(cfg: object) -> list[str]:
    raw = getattr(cfg, "stock_watchlist", "") + "," + getattr(cfg, "crypto_watchlist", "")
    return [s.strip() for s in raw.split(",") if s.strip()]


class KronosResearchAgent(MemoryMixin, AnalysisAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._predictor = None
        self._model_loaded = False
        self._load_error: str | None = None

    # ------------------------------------------------------------------ #
    #  Model loading (blocking — called in executor on first run)          #
    # ------------------------------------------------------------------ #

    def _load_model(self) -> None:
        try:
            from model import Kronos, KronosTokenizer, KronosPredictor  # noqa: F401
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            self.logger.info("kronos_loading", model=MODEL_ID, device=device)
            tokenizer = KronosTokenizer.from_pretrained(TOKENIZER_ID)
            model = Kronos.from_pretrained(MODEL_ID)
            self._predictor = KronosPredictor(model, tokenizer, max_context=2048)
            self._model_loaded = True
            self.logger.info("kronos_ready", device=device)
        except Exception as exc:
            self._load_error = str(exc)
            self.logger.error("kronos_load_failed", error=str(exc))

    # ------------------------------------------------------------------ #
    #  Main loop                                                            #
    # ------------------------------------------------------------------ #

    async def run_once(self) -> None:
        # Load model on first call
        if not self._model_loaded and self._load_error is None:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._load_model)

        if not self._model_loaded:
            self.logger.warning("kronos_skip_no_model", reason=self._load_error)
            return

        symbols = _watchlist(settings)
        if not symbols:
            self.logger.warning("kronos_no_symbols_configured")
            return

        symbol_data = await self._fetch_ohlcv(symbols)
        if not symbol_data:
            self.logger.warning("kronos_no_data_available")
            return

        now = datetime.now(timezone.utc)
        results = await self._predict_all(symbol_data)

        report_lines: list[str] = []
        for symbol, forecast in results.items():
            await self._store_forecast(symbol, forecast, now)
            await self.store_signal(
                symbol=symbol,
                signal_type=forecast["signal_type"],
                confidence=forecast["confidence"],
                reasoning=forecast["reasoning"],
                metadata={"source": "kronos", "pred_change_pct": forecast["pred_change_pct"]},
            )
            report_lines.append(_format_line(symbol, forecast))

        report_md = _build_report(report_lines, now, len(symbols))

        await self.write_to_obsidian(
            title=f"Kronos Forecast {now.strftime('%Y-%m-%d %H:%M')} UTC",
            body=report_md,
            tags=["kronos", "forecast", "research"],
        )
        await self.bus.publish("research.kronos", {
            "time": now.isoformat(),
            "symbol_count": len(results),
            "forecasts": {s: {k: v for k, v in f.items() if k != "reasoning"}
                          for s, f in results.items()},
            "report_md": report_md,
        })
        self.logger.info("kronos_complete", symbols_forecast=len(results))

    # ------------------------------------------------------------------ #
    #  Data fetching                                                        #
    # ------------------------------------------------------------------ #

    async def _fetch_ohlcv(self, symbols: list[str]) -> dict[str, pd.DataFrame]:
        out: dict[str, pd.DataFrame] = {}
        for symbol in symbols:
            rows = await self.db.fetch(
                """
                SELECT time, open, high, low, close, volume
                FROM prices
                WHERE symbol = $1
                ORDER BY time DESC
                LIMIT $2
                """,
                symbol, LOOKBACK,
            )
            if len(rows) < MIN_CANDLES:
                self.logger.info("kronos_skip_insufficient", symbol=symbol, rows=len(rows))
                continue
            df = pd.DataFrame([dict(r) for r in reversed(rows)])
            df["time"] = pd.to_datetime(df["time"])
            for col in ["open", "high", "low", "close", "volume"]:
                if col not in df.columns:
                    df[col] = 0.0
                df[col] = df[col].astype(float).fillna(0.0)
            out[symbol] = df
        return out

    # ------------------------------------------------------------------ #
    #  Prediction (runs in thread pool so it doesn't block event loop)    #
    # ------------------------------------------------------------------ #

    async def _predict_all(self, symbol_data: dict[str, pd.DataFrame]) -> dict[str, dict]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_predict_all, symbol_data)

    def _sync_predict_all(self, symbol_data: dict[str, pd.DataFrame]) -> dict[str, dict]:
        results: dict[str, dict] = {}
        for symbol, df in symbol_data.items():
            try:
                results[symbol] = self._predict_one(symbol, df)
            except Exception as exc:
                self.logger.warning("kronos_predict_failed", symbol=symbol, error=str(exc))
        return results

    def _predict_one(self, symbol: str, df: pd.DataFrame) -> dict:
        x_df = df[["open", "high", "low", "close", "volume"]].copy()
        x_ts = df["time"]

        # Infer candle frequency; fall back to hourly
        try:
            freq = pd.infer_freq(x_ts) or "1h"
        except Exception:
            freq = "1h"

        y_ts = pd.Series(pd.date_range(start=x_ts.iloc[-1], periods=PRED_LEN + 1, freq=freq)[1:])

        pred_df: pd.DataFrame = self._predictor.predict(
            df=x_df,
            x_timestamp=x_ts,
            y_timestamp=y_ts,
            pred_len=PRED_LEN,
            T=1.0,
            top_p=0.9,
            sample_count=3,
        )

        current_close = float(df["close"].iloc[-1])
        pred_close = float(pred_df["close"].iloc[-1])
        pred_high = float(pred_df["high"].max())
        pred_low = float(pred_df["low"].min())
        change_pct = ((pred_close - current_close) / current_close) * 100 if current_close else 0.0

        if change_pct > 0.5:
            sig = "bullish_signal"
        elif change_pct < -0.5:
            sig = "bearish_signal"
        else:
            sig = "neutral_signal"

        # Confidence: magnitude of move, clamped 30–85%
        conf = min(85.0, max(30.0, abs(change_pct) * 12))

        reasoning = (
            f"Kronos-mini ({PRED_LEN}-candle horizon): "
            f"current={current_close:.4f} → predicted={pred_close:.4f} "
            f"({change_pct:+.2f}%), range [{pred_low:.4f}–{pred_high:.4f}]. "
            f"Lookback={len(df)} candles."
        )

        return {
            "current_close": current_close,
            "pred_close": round(pred_close, 6),
            "pred_high": round(pred_high, 6),
            "pred_low": round(pred_low, 6),
            "pred_change_pct": round(change_pct, 3),
            "signal_type": sig,
            "confidence": round(conf, 1),
            "reasoning": reasoning,
            "lookback": len(df),
        }

    # ------------------------------------------------------------------ #
    #  Persistence                                                          #
    # ------------------------------------------------------------------ #

    async def _store_forecast(self, symbol: str, fc: dict, now: datetime) -> None:
        await self.db.execute(
            """
            INSERT INTO kronos_forecasts
                (time, symbol, model, lookback_candles, pred_horizon_candles,
                 pred_close, pred_change_pct, signal_type, confidence,
                 pred_high, pred_low, reasoning)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            now, symbol, MODEL_ID, fc["lookback"], PRED_LEN,
            fc["pred_close"], fc["pred_change_pct"],
            fc["signal_type"], fc["confidence"],
            fc["pred_high"], fc["pred_low"], fc["reasoning"],
        )


# ------------------------------------------------------------------ #
#  Report formatting helpers                                           #
# ------------------------------------------------------------------ #

def _format_line(symbol: str, fc: dict) -> str:
    arrow = "▲" if "bullish" in fc["signal_type"] else ("▼" if "bearish" in fc["signal_type"] else "◆")
    direction = fc["signal_type"].replace("_signal", "").upper()
    return (
        f"{arrow} {symbol:<12} {direction:<8} {fc['pred_change_pct']:>+7.2f}%  |  "
        f"now={fc['current_close']:.4f} => pred={fc['pred_close']:.4f}  "
        f"[{fc['pred_low']:.4f}–{fc['pred_high']:.4f}]  conf={fc['confidence']:.0f}%"
    )


def _build_report(lines: list[str], now: datetime, total_symbols: int) -> str:
    bullish = [l for l in lines if "▲" in l]
    bearish = [l for l in lines if "▼" in l]
    neutral = [l for l in lines if "◆" in l]

    parts = [
        f"## Kronos Foundation Model — Price Forecast Report",
        f"**Generated:** {now.strftime('%Y-%m-%d %H:%M UTC')}  "
        f"**Model:** {MODEL_ID}  **Horizon:** {PRED_LEN} candles",
        f"**Symbols attempted:** {total_symbols}  "
        f"**Forecasted:** {len(lines)}  "
        f"({len(bullish)} bullish · {len(bearish)} bearish · {len(neutral)} neutral)",
        "",
    ]
    if bullish:
        parts += ["### 🟢 Bullish Signals", "```"] + bullish + ["```", ""]
    if bearish:
        parts += ["### 🔴 Bearish Signals", "```"] + bearish + ["```", ""]
    if neutral:
        parts += ["### ⬜ Neutral", "```"] + neutral + ["```", ""]

    return "\n".join(parts)
