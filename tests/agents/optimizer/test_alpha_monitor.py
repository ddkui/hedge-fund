# tests/agents/optimizer/test_alpha_monitor.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_monitor():
    from agents.optimizer.alpha_monitor import AlphaMonitor
    m = AlphaMonitor.__new__(AlphaMonitor)
    m.name = "alpha_monitor"
    m.db = AsyncMock()
    m.bus = AsyncMock()
    m.logger = MagicMock()
    m._running = True
    m.interval_seconds = 86400
    m.write_to_obsidian = AsyncMock()
    return m


def test_beta_computation():
    from agents.optimizer.alpha_monitor import _compute_beta
    # SPY daily returns vary; portfolio return is exactly 2x SPY each day -> beta = 2
    spy_returns = [0.01, -0.02, 0.03, -0.01, 0.02]
    spy = [100.0]
    portfolio = [100.0]
    for r in spy_returns:
        spy.append(spy[-1] * (1 + r))
        portfolio.append(portfolio[-1] * (1 + 2 * r))
    beta = _compute_beta(portfolio, spy)
    assert abs(beta - 2.0) < 0.15


def test_jensens_alpha_positive():
    from agents.optimizer.alpha_monitor import _compute_jensens_alpha
    alpha = _compute_jensens_alpha(0.20, 0.10, 1.0)
    assert abs(alpha - 0.10) < 0.001


@pytest.mark.asyncio
async def test_tier_transitions_to_alpha_achieved():
    monitor = make_monitor()
    monitor.bus.get = AsyncMock(return_value={"tier": "learning"})
    monitor.bus.set = AsyncMock()
    monitor.bus.publish = AsyncMock()

    await monitor._classify_and_act(
        sharpe=1.6, jensens_alpha=0.03, beta=0.9,
        portfolio_annual=0.15, spy_annual=0.10
    )

    monitor.bus.set.assert_called()
    set_call = monitor.bus.set.call_args
    assert set_call[0][0] == "alpha:status"
    assert set_call[0][1]["tier"] == "alpha_achieved"


@pytest.mark.asyncio
async def test_exceptional_alpha_saves_strategy_to_obsidian():
    monitor = make_monitor()
    monitor.bus.get = AsyncMock(return_value={"tier": "alpha_achieved"})
    monitor.bus.set = AsyncMock()
    monitor.bus.publish = AsyncMock()

    await monitor._classify_and_act(
        sharpe=2.2, jensens_alpha=0.06, beta=0.8,
        portfolio_annual=0.25, spy_annual=0.12
    )

    monitor.write_to_obsidian.assert_called_once()
    call = monitor.write_to_obsidian.call_args
    assert "Exceptional" in call.kwargs["title"]


@pytest.mark.asyncio
async def test_alpha_erosion_resets_to_learning():
    monitor = make_monitor()
    monitor.bus.get = AsyncMock(return_value={"tier": "alpha_achieved"})
    monitor.bus.set = AsyncMock()
    monitor.bus.publish = AsyncMock()

    await monitor._classify_and_act(
        sharpe=0.9, jensens_alpha=-0.01, beta=1.1,
        portfolio_annual=0.05, spy_annual=0.08
    )

    set_call = monitor.bus.set.call_args
    assert set_call[0][1]["tier"] == "learning"
    # erosion email published
    assert monitor.bus.publish.called
