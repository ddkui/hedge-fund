import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from shared.backtester import BacktestTrade, Backtester


def test_backtest_trade_pnl_long():
    trade = BacktestTrade(
        symbol="AAPL", date=datetime(2024, 1, 1),
        action="long", entry_price=100.0, exit_price=110.0, quantity=10.0,
    )
    assert trade.calculate_pnl() == pytest.approx(100.0)


def test_backtest_trade_pnl_short():
    trade = BacktestTrade(
        symbol="AAPL", date=datetime(2024, 1, 1),
        action="short", entry_price=100.0, exit_price=90.0, quantity=10.0,
    )
    assert trade.calculate_pnl() == pytest.approx(100.0)


def test_backtester_win_rate_all_wins():
    bt = Backtester()
    trade = BacktestTrade(
        symbol="AAPL", date=datetime(2024, 1, 1),
        action="long", entry_price=100.0, exit_price=110.0, quantity=1.0,
    )
    trade.calculate_pnl()
    bt.add_trade(trade)
    metrics = bt.calculate_metrics()
    assert metrics["win_rate"] == 1.0
    assert metrics["total_pnl"] == pytest.approx(10.0)


def test_backtester_close_trade():
    bt = Backtester()
    bt.add_trade(BacktestTrade(symbol="AAPL", date=datetime(2024, 1, 1), action="long", entry_price=100.0))
    bt.close_trade("AAPL", exit_price=120.0)
    metrics = bt.calculate_metrics()
    assert metrics["total_pnl"] == pytest.approx(20.0)


def _make_series(n: int = 100) -> tuple:
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    prices = pd.Series(np.linspace(100.0, 130.0, n), index=dates)
    entries = pd.Series(False, index=dates)
    exits = pd.Series(False, index=dates)
    entries.iloc[10] = True
    exits.iloc[20] = True
    entries.iloc[40] = True
    exits.iloc[50] = True
    return prices, entries, exits


def test_vector_backtester_run_returns_all_metrics():
    bt = Backtester()
    prices, entries, exits = _make_series()
    metrics = bt.run(prices, entries, exits)
    for key in ("sharpe_ratio", "max_drawdown", "win_rate", "total_return"):
        assert key in metrics, f"missing metric: {key}"


def test_vector_backtester_total_return_positive_uptrend():
    bt = Backtester()
    prices, entries, exits = _make_series()
    metrics = bt.run(prices, entries, exits)
    assert metrics["total_return"] >= 0.0


def test_vector_backtester_walk_forward_splits():
    bt = Backtester()
    prices, entries, exits = _make_series(200)
    result = bt.walk_forward(prices, entries, exits)
    assert "in_sample" in result
    assert "out_of_sample" in result
    for key in ("sharpe_ratio", "max_drawdown", "total_return"):
        assert key in result["in_sample"]
        assert key in result["out_of_sample"]


def test_vector_backtester_no_trades_returns_safe_defaults():
    bt = Backtester()
    dates = pd.date_range("2024-01-01", periods=50, freq="D")
    prices = pd.Series(np.linspace(100.0, 110.0, 50), index=dates)
    entries = pd.Series(False, index=dates)
    exits = pd.Series(False, index=dates)
    metrics = bt.run(prices, entries, exits)
    assert isinstance(metrics, dict)
    assert metrics.get("total_return", 0.0) == pytest.approx(0.0, abs=1e-6)
