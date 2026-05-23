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
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    from datetime import datetime, timezone, timedelta
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)

    # VaR call data (open_symbols only: MSFT, GOOGL — returns empty so VaR passes)
    var_rows = []

    # Correlation call data (all_symbols: MSFT, GOOGL, AAPL)
    corr_rows = [
        {"symbol": s, "time": base_time + timedelta(days=i), "close": float(100 + i)}
        for i in range(30)
        for s in ["MSFT", "GOOGL", "AAPL"]
    ]

    db.fetch = AsyncMock(side_effect=[var_rows, corr_rows])

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


@pytest.mark.asyncio
async def test_checker_rejects_var_breach():
    checker = make_checker(var_limit_pct=0.02)  # 2% limit
    db = AsyncMock()
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)  # no cache

    # Build a price series for one symbol with large drops (5th pct of daily returns << -2%)
    # 30 rows: price drops by 3% on most days
    import numpy as np
    np.random.seed(99)
    from datetime import datetime, timezone, timedelta
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    prices = [100.0]
    for i in range(29):
        # Mostly flat but with large drops
        prices.append(prices[-1] * (1 + np.random.choice([-0.04, -0.03, 0.01, 0.02], p=[0.4, 0.3, 0.2, 0.1])))

    rows = [
        {"symbol": "MSFT", "time": base_time + timedelta(days=i), "close": prices[i]}
        for i in range(30)
    ]
    db.fetch = AsyncMock(return_value=rows)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=100.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=1,
        open_symbols=["MSFT"],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "var" in reason
