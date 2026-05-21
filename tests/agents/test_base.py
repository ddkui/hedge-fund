import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timezone
from agents.base import AnalysisAgent


class ConcreteAgent(AnalysisAgent):
    async def run_once(self):
        pass


def make_agent():
    return ConcreteAgent(
        name="test_analysis",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_store_signal_calls_execute():
    agent = make_agent()
    await agent.store_signal(
        symbol="AAPL",
        signal_type="momentum",
        confidence=75.0,
        reasoning="RSI crossed above 50 with MACD bullish",
        metadata={"rsi": 58.3, "macd": 0.42},
    )
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "AAPL" in call[0][1:]
    assert 75.0 in call[0][1:]


@pytest.mark.asyncio
async def test_store_signal_publishes_to_bus():
    agent = make_agent()
    await agent.store_signal(
        symbol="BTC",
        signal_type="sentiment",
        confidence=82.0,
        reasoning="Strong positive sentiment",
    )
    agent.bus.publish.assert_called_once()
    call = agent.bus.publish.call_args
    assert call[0][0] == "signals.test_analysis"
    assert call[0][1]["symbol"] == "BTC"
    assert call[0][1]["confidence"] == 82.0


@pytest.mark.asyncio
async def test_store_signal_none_symbol_allowed():
    agent = make_agent()
    await agent.store_signal(
        symbol=None,
        signal_type="macro_regime",
        confidence=90.0,
        reasoning="Fed hiking cycle detected",
    )
    agent.db.execute.assert_called_once()
