import pytest
import numpy as np
from unittest.mock import AsyncMock
from agents.quant.mean_reversion.agent import MeanReversionQuantAgent


def make_agent():
    return MeanReversionQuantAgent(
        name="mean_reversion",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        watchlist=["AAPL"],
        interval_seconds=120,
    )


def make_rows_zscore(target_zscore=2.5):
    """Last bar is target_zscore std devs above/below 20-bar rolling mean.

    Creates a trend first to push RSI to extreme values, then a spike to achieve
    the target zscore. This ensures RSI confirmation works properly.
    """
    np.random.seed(42)
    prices = []
    price = 150.0

    # Create a trend based on zscore direction to push RSI extreme
    trend_direction = 1.0 if target_zscore > 0 else -1.0

    # 40 bars of trend to build up momentum
    for i in range(40):
        price += trend_direction * (0.5 + np.random.normal(0, 0.1))
        prices.append(price)

    # 9 more bars with smaller moves
    for i in range(9):
        price += trend_direction * (0.2 + np.random.normal(0, 0.05))
        prices.append(price)

    # Final spike to achieve target zscore
    mean_20 = np.mean(prices[-20:])
    std_20 = np.std(prices[-20:])
    if std_20 == 0:
        std_20 = 1.0
    final = mean_20 + target_zscore * std_20
    prices.append(final)

    return [{"close": p, "time": None} for p in prices]


@pytest.mark.asyncio
async def test_mean_reversion_bearish_on_high_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(target_zscore=2.5))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "reversion_bearish" in call[0]


@pytest.mark.asyncio
async def test_mean_reversion_bullish_on_low_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(target_zscore=-2.5))
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "reversion_bullish" in call[0]


@pytest.mark.asyncio
async def test_mean_reversion_skips_normal_zscore():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=make_rows_zscore(target_zscore=0.5))
    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_mean_reversion_skips_insufficient_data():
    agent = make_agent()
    # Create simple 15-bar data with no signal (just noise)
    np.random.seed(42)
    small_data = [{"close": 150.0 + np.random.normal(0, 0.5), "time": None} for _ in range(15)]
    agent.db.fetch = AsyncMock(return_value=small_data)
    await agent.run_once()
    agent.db.execute.assert_not_called()
