import pytest
import pandas as pd
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
from agents.technical.agent import TechnicalAnalysisAgent


def make_agent(watchlist=None):
    return TechnicalAnalysisAgent(
        name="technical",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=watchlist or ["AAPL"],
        interval_seconds=60,
    )


def make_price_rows(n=50, symbol="AAPL", close_start=150.0):
    np.random.seed(7)
    closes = close_start + np.cumsum(np.random.normal(0, 1.5, n))
    rows = []
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    for i in range(n):
        rows.append({
            "time": base.replace(minute=i % 60, hour=10 + i // 60),
            "open": closes[i] - 0.2,
            "high": closes[i] + 0.5,
            "low": closes[i] - 0.5,
            "close": closes[i],
            "volume": 100_000.0,
        })
    return rows


@pytest.mark.asyncio
async def test_technical_agent_stores_signal_for_symbol():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "AAPL"))
    await agent.run_once()
    assert agent.db.execute.call_count >= 1
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "AAPL" in call[0]


@pytest.mark.asyncio
async def test_technical_agent_publishes_signal():
    agent = make_agent(["MSFT"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "MSFT"))
    await agent.run_once()
    agent.bus.publish.assert_called()
    calls = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.technical" in c for c in calls)


@pytest.mark.asyncio
async def test_technical_agent_skips_insufficient_data():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(5, "AAPL"))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_technical_agent_signal_confidence_in_range():
    agent = make_agent(["AAPL"])
    agent.db.fetch = AsyncMock(return_value=make_price_rows(50, "AAPL"))
    await agent.run_once()
    call = agent.db.execute.call_args
    confidence = call[0][5]
    assert 0.0 <= confidence <= 100.0
