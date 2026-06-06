import pytest
import pandas as pd
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta


def make_agent():
    from agents.quant.kronos.agent import KronosResearchAgent
    agent = KronosResearchAgent.__new__(KronosResearchAgent)
    agent.name = "kronos"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.bus.publish = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent.write_to_obsidian = AsyncMock()
    agent._model_loaded = False
    agent._load_error = None
    agent._predictor = None
    agent.interval_seconds = 21600
    agent._running = True
    return agent


def _make_ohlcv_rows(n=60):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {
            "time": base + timedelta(hours=i),
            "open": 100.0 + i * 0.1,
            "high": 101.0 + i * 0.1,
            "low": 99.0 + i * 0.1,
            "close": 100.5 + i * 0.1,
            "volume": 1000.0,
        }
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_skip_when_model_not_loaded():
    agent = make_agent()
    agent._load_error = "torch not available"
    await agent.run_once()
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_skip_symbol_with_insufficient_data():
    agent = make_agent()
    agent._model_loaded = True
    agent._predictor = MagicMock()
    # Return only 10 rows — below MIN_CANDLES (50)
    agent.db.fetch = AsyncMock(return_value=_make_ohlcv_rows(10))
    with patch("agents.quant.kronos.agent.settings") as mock_settings:
        mock_settings.stock_watchlist = "AAPL"
        mock_settings.crypto_watchlist = ""
        await agent.run_once()
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_predict_one_bullish():
    from agents.quant.kronos.agent import KronosResearchAgent
    agent = make_agent()
    agent._model_loaded = True

    rows = _make_ohlcv_rows(60)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])

    # Mock predictor: returns a DataFrame where final close > current close
    current_close = df["close"].iloc[-1]
    pred_close = current_close * 1.03  # +3% → bullish

    pred_rows = _make_ohlcv_rows(24)
    pred_df = pd.DataFrame(pred_rows)
    pred_df["close"] = pred_close
    pred_df["high"] = pred_close * 1.01
    pred_df["low"] = pred_close * 0.99

    mock_predictor = MagicMock()
    mock_predictor.predict.return_value = pred_df
    agent._predictor = mock_predictor

    result = agent._predict_one("AAPL", df)

    assert result["signal_type"] == "bullish_signal"
    assert result["pred_change_pct"] > 0
    assert result["confidence"] >= 30.0


@pytest.mark.asyncio
async def test_predict_one_bearish():
    agent = make_agent()
    agent._model_loaded = True

    rows = _make_ohlcv_rows(60)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])

    current_close = df["close"].iloc[-1]
    pred_close = current_close * 0.96  # -4% → bearish

    pred_rows = _make_ohlcv_rows(24)
    pred_df = pd.DataFrame(pred_rows)
    pred_df["close"] = pred_close
    pred_df["high"] = pred_close * 1.005
    pred_df["low"] = pred_close * 0.995

    agent._predictor = MagicMock()
    agent._predictor.predict.return_value = pred_df

    result = agent._predict_one("BTCUSDT", df)

    assert result["signal_type"] == "bearish_signal"
    assert result["pred_change_pct"] < 0


@pytest.mark.asyncio
async def test_predict_one_neutral():
    agent = make_agent()
    agent._model_loaded = True

    rows = _make_ohlcv_rows(60)
    df = pd.DataFrame(rows)
    df["time"] = pd.to_datetime(df["time"])

    current_close = df["close"].iloc[-1]
    pred_close = current_close * 1.001  # +0.1% → neutral

    pred_df = pd.DataFrame(_make_ohlcv_rows(24))
    pred_df["close"] = pred_close
    pred_df["high"] = pred_close
    pred_df["low"] = pred_close

    agent._predictor = MagicMock()
    agent._predictor.predict.return_value = pred_df

    result = agent._predict_one("MSFT", df)

    assert result["signal_type"] == "neutral_signal"


@pytest.mark.asyncio
async def test_store_forecast_calls_db_execute():
    agent = make_agent()
    agent.db.execute = AsyncMock()
    now = datetime.now(timezone.utc)
    fc = {
        "lookback": 60, "pred_close": 185.0, "pred_change_pct": 2.5,
        "signal_type": "bullish_signal", "confidence": 70.0,
        "pred_high": 186.0, "pred_low": 184.0, "reasoning": "test",
    }
    await agent._store_forecast("AAPL", fc, now)
    agent.db.execute.assert_called_once()
    call_sql = agent.db.execute.call_args[0][0]
    assert "kronos_forecasts" in call_sql


@pytest.mark.asyncio
async def test_full_run_with_mocked_predictor():
    agent = make_agent()
    agent._model_loaded = True

    rows = _make_ohlcv_rows(60)
    current_close = rows[-1]["close"]
    pred_close = current_close * 1.025

    pred_df = pd.DataFrame(_make_ohlcv_rows(24))
    pred_df["close"] = pred_close
    pred_df["high"] = pred_close * 1.01
    pred_df["low"] = pred_close * 0.99

    mock_predictor = MagicMock()
    mock_predictor.predict.return_value = pred_df
    agent._predictor = mock_predictor

    agent.db.fetch = AsyncMock(return_value=rows)
    agent.db.execute = AsyncMock()

    with patch("agents.quant.kronos.agent.settings") as mock_settings:
        mock_settings.stock_watchlist = "AAPL"
        mock_settings.crypto_watchlist = ""
        await agent.run_once()

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["symbol"] == "AAPL"
    assert call.kwargs["signal_type"] == "bullish_signal"
    agent.write_to_obsidian.assert_called_once()
    agent.bus.publish.assert_called_once()
    channel = agent.bus.publish.call_args[0][0]
    assert channel == "research.kronos"


def test_format_report_line_bullish():
    from agents.quant.kronos.agent import _format_line
    fc = {
        "signal_type": "bullish_signal", "pred_change_pct": 2.5,
        "current_close": 100.0, "pred_close": 102.5,
        "pred_low": 101.0, "pred_high": 103.0, "confidence": 70.0,
    }
    line = _format_line("AAPL", fc)
    assert "▲" in line
    assert "BULLISH" in line
    assert "+2.50%" in line


def test_build_report_sections():
    from agents.quant.kronos.agent import _build_report, _format_line
    now = datetime(2026, 6, 6, 12, 0, tzinfo=timezone.utc)
    bullish_fc = {
        "signal_type": "bullish_signal", "pred_change_pct": 2.0,
        "current_close": 100.0, "pred_close": 102.0,
        "pred_low": 101.0, "pred_high": 103.0, "confidence": 65.0,
    }
    bearish_fc = {
        "signal_type": "bearish_signal", "pred_change_pct": -1.5,
        "current_close": 50000.0, "pred_close": 49250.0,
        "pred_low": 49000.0, "pred_high": 50000.0, "confidence": 55.0,
    }
    lines = [_format_line("AAPL", bullish_fc), _format_line("BTC", bearish_fc)]
    report = _build_report(lines, now, total_symbols=3)
    assert "Kronos" in report
    assert "Bullish" in report
    assert "Bearish" in report
    assert "2026-06-06" in report
