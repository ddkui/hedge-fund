# tests/agents/quant/test_news_momentum.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_agent():
    from agents.quant.news_momentum.agent import NewsMomentumAgent
    agent = NewsMomentumAgent.__new__(NewsMomentumAgent)
    agent.name = "news_momentum"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent._running = True
    agent.interval_seconds = 120
    agent.watchlist = ["AAPL", "MSFT"]
    return agent


@pytest.mark.asyncio
async def test_bullish_when_both_agree():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bullish_signal", "confidence": 80.0
    })
    prices = [{"close": 100.0 + i * 0.1} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bullish_signal"


@pytest.mark.asyncio
async def test_neutral_when_directions_diverge():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bearish_signal", "confidence": 70.0
    })
    prices = [{"close": 100.0 + i * 0.2} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_skips_when_no_recent_sentiment():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value=None)
    prices = [{"close": 100.0} for _ in range(20)]
    agent.db.fetch = AsyncMock(return_value=prices)

    await agent._analyze("AAPL", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_bearish_when_both_agree_negative():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bearish_signal", "confidence": 75.0
    })
    prices = [{"close": 110.0 - i * 0.3} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "bearish_signal"


@pytest.mark.asyncio
async def test_confidence_bounded():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "signal_type": "bullish_signal", "confidence": 100.0
    })
    prices = [{"close": 100.0 + i * 5} for i in range(20)]
    agent.db.fetch = AsyncMock(return_value=list(reversed(prices)))

    await agent._analyze("AAPL", "expansion")

    call = agent.store_signal.call_args
    assert call.kwargs["confidence"] <= 85.0
    assert call.kwargs["confidence"] >= 0.0
