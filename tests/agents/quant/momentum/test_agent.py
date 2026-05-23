import pytest
from unittest.mock import AsyncMock
from agents.quant.momentum.agent import MomentumQuantAgent


def make_agent():
    return MomentumQuantAgent(
        name="momentum",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=["AAPL"],
        interval_seconds=120,
    )


def make_rows(n=70, trend="up"):
    price = 150.0
    rows = []
    for i in range(n):
        price += 0.1 if trend == "up" else -0.1
        rows.append({"close": price, "time": None})
    return rows


@pytest.mark.asyncio
async def test_momentum_stores_bullish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "up"))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]
    assert "momentum_bullish" in call[0]


@pytest.mark.asyncio
async def test_momentum_stores_bearish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "down"))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "momentum_bearish" in call[0]


@pytest.mark.asyncio
async def test_momentum_skips_insufficient_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(30, "up"))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_momentum_confidence_in_range():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows(70, "up"))
    await agent.run_once()
    call = agent.db.execute.call_args
    confidence = call[0][5]
    assert 0.0 <= confidence <= 100.0
