# tests/agents/portfolio_researcher/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_agent():
    from agents.portfolio_researcher.agent import PortfolioResearcherAgent
    agent = PortfolioResearcherAgent.__new__(PortfolioResearcherAgent)
    agent.name = "portfolio_researcher"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.bus.get = AsyncMock(return_value=None)
    agent.logger = MagicMock()
    agent._running = True
    agent.interval_seconds = 1800
    return agent


@pytest.mark.asyncio
async def test_researcher_skips_when_no_open_positions():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_researcher_emits_hold_for_bullish_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        # open positions
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        # signals for AAPL
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish_signal", "confidence": 70.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    agent.store_signal.assert_called_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "hold"
    assert call.kwargs["symbol"] == "AAPL"


@pytest.mark.asyncio
async def test_researcher_emits_sell_for_contradicted_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bearish_signal", "confidence": 75.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "sell"


@pytest.mark.asyncio
async def test_researcher_emits_trim_for_weakening_position():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [{"id": 1, "symbol": "AAPL", "direction": "long", "entry_thesis": "bullish momentum"}],
        [{"agent": "aggregator", "symbol": "AAPL", "signal_type": "bullish_signal", "confidence": 38.0}],
    ])
    agent.store_signal = AsyncMock()
    await agent.run_once()
    call = agent.store_signal.call_args
    assert call.kwargs["signal_type"] == "trim"
