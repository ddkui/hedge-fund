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
    args = call[0][1:]  # skip the SQL string
    assert args[1] == "test_analysis"   # $2 agent name
    assert args[2] == "AAPL"            # $3 symbol
    assert args[3] == "momentum"        # $4 signal_type
    assert args[4] == 75.0              # $5 confidence


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
    agent.bus.publish.assert_called_once()
    pub_call = agent.bus.publish.call_args
    assert pub_call[0][1]["symbol"] is None
    # Verify None goes into the $3 slot
    exec_args = agent.db.execute.call_args[0][1:]
    assert exec_args[2] is None  # $3 symbol
