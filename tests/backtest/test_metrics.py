import pytest
from datetime import datetime, timezone, timedelta
from backtest.metrics import compute_metrics


def _dt(days):
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=days)


def _snap(day, total_value, cash=None):
    v = total_value
    return {
        "time": _dt(day),
        "total_value": v,
        "cash": cash if cash is not None else v,
        "peak_value": v,
    }


def test_total_return_flat():
    snaps = [_snap(0, 100_000), _snap(1, 100_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_return_pct"] == pytest.approx(0.0)


def test_total_return_positive():
    snaps = [_snap(0, 100_000), _snap(365, 120_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_return_pct"] == pytest.approx(20.0)


def test_max_drawdown_none():
    snaps = [_snap(i, 100_000 + i * 1000) for i in range(5)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["max_drawdown_pct"] == pytest.approx(0.0)


def test_max_drawdown_simple():
    """Peak=120k, trough=90k → drawdown = (120k-90k)/120k = 25%."""
    snaps = [
        _snap(0, 100_000),
        _snap(1, 120_000),
        _snap(2, 90_000),
        _snap(3, 100_000),
    ]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["max_drawdown_pct"] == pytest.approx(25.0, abs=0.1)


def test_cagr_one_year_twenty_pct():
    snaps = [_snap(0, 100_000), _snap(365, 120_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["cagr_pct"] == pytest.approx(20.0, abs=0.2)


def test_sharpe_zero_for_flat():
    """All returns = 0 → Sharpe = 0.0."""
    snaps = [_snap(i, 100_000) for i in range(10)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["sharpe_ratio"] == pytest.approx(0.0)


def test_total_trades_count():
    snaps = [_snap(0, 100_000), _snap(1, 105_000)]
    trades = [{"action": "long"}, {"action": "close"}, {"action": "short"}]
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_trades"] == 3


def test_final_value():
    snaps = [_snap(0, 100_000), _snap(1, 115_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["final_value"] == pytest.approx(115_000.0)
