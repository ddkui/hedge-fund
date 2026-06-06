# tests/agents/quant/test_vwap.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta


def make_agent():
    from agents.quant.vwap.agent import VWAPDeviationAgent
    agent = VWAPDeviationAgent.__new__(VWAPDeviationAgent)
    agent.name = "vwap"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent._running = True
    agent.interval_seconds = 120
    agent.watchlist = ["AAPL", "BTCUSDT"]
    return agent


def _make_candles(n, base_price, base_volume=1000.0):
    now = datetime.now(timezone.utc)
    return [
        {"close": base_price, "volume": base_volume,
         "time": now - timedelta(minutes=n - i)}
        for i in range(n)
    ]


@pytest.mark.asyncio
async def test_bullish_when_price_below_vwap():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[-1] = {**candles[-1], "close": 97.0}  # current (last) 3% below VWAP
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bullish_signal"


@pytest.mark.asyncio
async def test_bearish_when_price_above_vwap():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[-1] = {**candles[-1], "close": 103.0}
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bearish_signal"


@pytest.mark.asyncio
async def test_neutral_within_threshold():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[-1] = {**candles[-1], "close": 100.3}
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_skips_insufficient_candles():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=_make_candles(3, 100.0))

    await agent._analyze("AAPL", "stock", "expansion")
    agent.store_signal.assert_not_called()


def test_vwap_calculation_correct():
    from agents.quant.vwap.agent import _compute_vwap
    candles = [
        {"close": 100.0, "volume": 200.0},
        {"close": 110.0, "volume": 100.0},
    ]
    vwap = _compute_vwap(candles)
    assert abs(vwap - 103.333) < 0.01


@pytest.mark.asyncio
async def test_confidence_scales_with_deviation():
    agent = make_agent()
    candles = _make_candles(20, 100.0)
    candles[-1] = {**candles[-1], "close": 90.0}  # 10% below
    agent.db.fetch = AsyncMock(return_value=candles)

    await agent._analyze("AAPL", "stock", "expansion")

    call = agent.store_signal.call_args
    assert call.kwargs["confidence"] > 60.0
    assert call.kwargs["confidence"] <= 80.0
