import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call


def _dt(hour):
    return datetime(2024, 1, 1, hour, tzinfo=timezone.utc)


def _make_runner(agent_names=None):
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus
    from backtest.runner import BacktestRunner

    clock = BacktestClock(
        start=_dt(0), end=_dt(2), step_seconds=3600
    )

    mock_db = AsyncMock()
    mock_db.current_tick = None
    mock_db.set_tick = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()

    if agent_names is None:
        agent_names = []

    return BacktestRunner(
        run_id=1,
        clock=clock,
        db=mock_db,
        bus=bus,
        agent_names=agent_names,
    ), mock_db


async def test_set_tick_called_per_tick():
    runner, mock_db = _make_runner()
    await runner.run()
    # 3 ticks: 00:00, 01:00, 02:00
    assert mock_db.set_tick.call_count == 3


async def test_portfolio_state_seeded_at_first_tick():
    runner, mock_db = _make_runner()
    await runner.run()

    insert_calls = [
        c for c in mock_db.execute.call_args_list
        if "portfolio_state" in str(c) and "INSERT" in str(c)
    ]
    assert len(insert_calls) >= 1


async def test_ticks_advance_in_order():
    runner, mock_db = _make_runner()
    await runner.run()

    tick_calls = [c.args[0] for c in mock_db.set_tick.call_args_list]
    assert tick_calls == [_dt(0), _dt(1), _dt(2)]


async def test_agent_run_once_called_per_tick():
    """Each agent's run_once() is called once per tick."""
    from backtest.runner import BacktestRunner
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus

    mock_db = AsyncMock()
    mock_db.current_tick = _dt(0)
    mock_db.set_tick = AsyncMock(side_effect=lambda dt: setattr(mock_db, 'current_tick', dt))
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()
    clock = BacktestClock(start=_dt(0), end=_dt(1), step_seconds=3600)

    mock_agent = AsyncMock()
    mock_agent.run_once = AsyncMock()
    mock_agent._now = lambda: mock_db.current_tick

    runner = BacktestRunner(
        run_id=1, clock=clock, db=mock_db, bus=bus, agent_names=[]
    )
    runner._tiers = [[mock_agent]]

    await runner.run()

    # 2 ticks → run_once called twice
    assert mock_agent.run_once.call_count == 2


async def test_agent_error_does_not_crash_run():
    """A failing agent should log and continue; the run must complete."""
    from backtest.runner import BacktestRunner
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus

    mock_db = AsyncMock()
    mock_db.current_tick = _dt(0)
    mock_db.set_tick = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()
    clock = BacktestClock(start=_dt(0), end=_dt(0), step_seconds=3600)

    mock_agent = AsyncMock()
    mock_agent.run_once = AsyncMock(side_effect=RuntimeError("agent exploded"))
    mock_agent._now = lambda: mock_db.current_tick

    runner = BacktestRunner(
        run_id=1, clock=clock, db=mock_db, bus=bus, agent_names=[]
    )
    runner._tiers = [[mock_agent]]

    # Must not raise
    await runner.run()
