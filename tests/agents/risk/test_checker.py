import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from agents.risk.checker import RiskChecker


def make_checker(
    portfolio_value=100_000.0,
    peak_value=100_000.0,
    open_positions=2,
    max_position_pct=0.10,
    max_positions=10,
    max_drawdown_pct=0.20,
    var_limit_pct=0.05,
    max_correlated=3,
):
    settings = MagicMock()
    settings.risk_max_position_pct = max_position_pct
    settings.risk_max_positions = max_positions
    settings.risk_max_drawdown_pct = max_drawdown_pct
    settings.risk_var_limit_pct = var_limit_pct
    settings.risk_max_correlated = max_correlated
    return RiskChecker(settings=settings)


@pytest.mark.asyncio
async def test_checker_approves_valid_trade():
    checker = make_checker()
    db = AsyncMock()
    # No open positions; simple price series for var
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=5.0,
        price=150.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is True
    assert reason == ""


@pytest.mark.asyncio
async def test_checker_rejects_oversized_position():
    checker = make_checker(max_position_pct=0.10)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=100.0,     # 100 * 200 = 20_000 = 20% of 100k
        price=200.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "position_size" in reason


@pytest.mark.asyncio
async def test_checker_rejects_too_many_positions():
    checker = make_checker(max_positions=3)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=100.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=3,     # already at max
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "open_positions" in reason


@pytest.mark.asyncio
async def test_checker_rejects_drawdown_breach():
    checker = make_checker(max_drawdown_pct=0.20)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=100.0,
        portfolio_value=75_000.0,   # 25% drawdown from 100k peak
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "drawdown" in reason


@pytest.mark.asyncio
async def test_checker_rejects_correlated_positions():
    checker = make_checker(max_correlated=2)
    db = AsyncMock()
    # Return price series for 2 existing symbols + proposed — all highly correlated
    prices_up = [{"symbol": s, "close": float(100 + i)} for i in range(30) for s in ["MSFT", "GOOGL"]]
    # proposed AAPL is also rising — all three corr > 0.7
    db.fetch = AsyncMock(return_value=prices_up + [{"symbol": "AAPL", "close": float(100 + i)} for i in range(30)])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=130.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=["MSFT", "GOOGL"],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "correlation" in reason
