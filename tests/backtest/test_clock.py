import pytest
from datetime import datetime, timezone, timedelta
from backtest.clock import BacktestClock


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_single_tick():
    """Start == end yields exactly one tick."""
    start = _dt(2024, 1, 1)
    clock = BacktestClock(start=start, end=start, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks == [start]


def test_two_ticks():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 1)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks == [start, end]


def test_tick_count_one_day_hourly():
    """One day at 1h step = 25 ticks (00:00 through 24:00)."""
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 2, 0)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert len(ticks) == 25


def test_step_accuracy():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 2)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks[1] - ticks[0] == timedelta(hours=1)


def test_end_boundary_included():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 3)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks[-1] == end


def test_len():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 4)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    assert len(clock) == 5


def test_end_before_start_yields_nothing():
    start = _dt(2024, 1, 2)
    end = _dt(2024, 1, 1)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    assert list(clock.ticks()) == []
