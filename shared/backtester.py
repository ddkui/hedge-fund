# shared/backtester.py
"""
Backtesting and replay - simulate historical signals against past prices.
Compare paper vs real execution.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import numpy as np
import pandas as pd


@dataclass
class BacktestTrade:
    symbol: str
    date: datetime
    action: str  # "long" or "short"
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float = 1.0
    pnl: Optional[float] = None
    returns_pct: Optional[float] = None

    def calculate_pnl(self) -> Optional[float]:
        if self.exit_price is None:
            return None
        pnl = (self.exit_price - self.entry_price) * self.quantity
        if self.action == "short":
            pnl = -pnl
        self.pnl = pnl
        return pnl

    def calculate_returns_pct(self) -> Optional[float]:
        if self.entry_price == 0:
            return None
        returns = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        if self.action == "short":
            returns = -returns
        self.returns_pct = returns
        return returns


class Backtester:
    def __init__(
        self,
        slippage: float = 0.001,
        fees: float = 0.001,
        init_cash: float = 100_000.0,
        is_ratio: float = 0.7,
    ):
        self.trades: list[BacktestTrade] = []
        self.starting_capital = init_cash
        self.current_cash = init_cash
        self.slippage = slippage
        self.fees = fees
        self.is_ratio = is_ratio

    def add_trade(self, trade: BacktestTrade) -> None:
        self.trades.append(trade)

    def close_trade(self, symbol: str, exit_price: float) -> None:
        open_trades = [t for t in self.trades if t.symbol == symbol and t.exit_price is None]
        if open_trades:
            open_trades[0].exit_price = exit_price
            open_trades[0].calculate_pnl()
            open_trades[0].calculate_returns_pct()

    def _compute_metrics(self, returns: pd.Series) -> dict:
        """Compute Sharpe, max drawdown, calmar, annual return from a returns series."""
        if returns.empty or returns.sum() == 0:
            return {
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
                "calmar_ratio": 0.0,
                "annual_return": 0.0,
                "total_return": 0.0,
                "win_rate": 0.0,
            }
        try:
            import empyrical
            sharpe = float(empyrical.sharpe_ratio(returns, annualization=252) or 0.0)
            max_dd = float(empyrical.max_drawdown(returns) or 0.0)
            calmar = float(empyrical.calmar_ratio(returns, annualization=252) or 0.0)
            annual = float(empyrical.annual_return(returns, annualization=252) or 0.0)
        except Exception:
            sharpe = 0.0
            max_dd = float((returns.cumsum().cummax() - returns.cumsum()).max() or 0.0)
            calmar = 0.0
            annual = 0.0

        total_return = float(returns.sum())
        win_rate = float((returns > 0).sum() / len(returns)) if len(returns) > 0 else 0.0

        return {
            "sharpe_ratio": sharpe,
            "max_drawdown": max_dd,
            "calmar_ratio": calmar,
            "annual_return": annual,
            "total_return": total_return,
            "win_rate": win_rate,
        }

    def run(
        self,
        prices: pd.Series,
        entries: pd.Series,
        exits: pd.Series,
    ) -> dict:
        """
        Simulate entries/exits on a price series with slippage and fees applied.
        Returns performance metrics dict.
        """
        if prices.empty:
            return {"sharpe_ratio": 0.0, "max_drawdown": 0.0, "calmar_ratio": 0.0,
                    "annual_return": 0.0, "total_return": 0.0, "win_rate": 0.0}

        portfolio_returns = []
        in_position = False
        entry_price = None

        for i, (date, price) in enumerate(prices.items()):
            if not in_position and entries.get(date, False):
                # Apply slippage and fees on entry
                entry_price = price * (1 + self.slippage + self.fees)
                in_position = True
            elif in_position and exits.get(date, False):
                # Apply slippage and fees on exit
                exit_price = price * (1 - self.slippage - self.fees)
                ret = (exit_price - entry_price) / entry_price
                portfolio_returns.append(ret)
                in_position = False
                entry_price = None

        returns_series = pd.Series(portfolio_returns, dtype=float)
        metrics = self._compute_metrics(returns_series)
        metrics["num_trades"] = len(portfolio_returns)
        return metrics

    def walk_forward(
        self,
        prices: pd.Series,
        entries: pd.Series,
        exits: pd.Series,
        n_splits: int = 5,
    ) -> dict:
        """
        Walk-forward validation: split into in-sample / out-of-sample windows.
        Returns aggregated metrics for each.
        """
        n = len(prices)
        split = int(n * self.is_ratio)

        in_prices = prices.iloc[:split]
        in_entries = entries.iloc[:split]
        in_exits = exits.iloc[:split]

        out_prices = prices.iloc[split:]
        out_entries = entries.iloc[split:]
        out_exits = exits.iloc[split:]

        return {
            "in_sample": self.run(in_prices, in_entries, in_exits),
            "out_of_sample": self.run(out_prices, out_entries, out_exits),
        }

    def calculate_metrics(self) -> dict:
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return {}

        total_pnl = sum(t.pnl for t in closed)
        winning_trades = len([t for t in closed if t.pnl > 0])
        losing_trades = len([t for t in closed if t.pnl <= 0])
        win_rate = winning_trades / len(closed) if closed else 0

        result = {
            "total_trades": len(closed),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_returns_pct": (total_pnl / self.starting_capital) * 100,
        }

        if len(closed) >= 2:
            try:
                import empyrical
                trade_returns = pd.Series([
                    t.pnl / (t.entry_price * t.quantity)
                    if t.entry_price * t.quantity != 0 else 0.0
                    for t in closed
                ])
                result["sharpe_ratio"] = float(empyrical.sharpe_ratio(trade_returns) or 0.0)
                result["max_drawdown"] = float(empyrical.max_drawdown(trade_returns) or 0.0)
                result["calmar_ratio"] = float(empyrical.calmar_ratio(trade_returns) or 0.0)
                result["annual_return"] = float(empyrical.annual_return(trade_returns) or 0.0)
            except Exception:
                pass

        return result

    def compare_paper_vs_real(
        self,
        paper_trades: list[BacktestTrade],
        real_trades: list[BacktestTrade],
    ) -> dict:
        paper_pnl = sum(t.pnl for t in paper_trades if t.pnl is not None)
        real_pnl = sum(t.pnl for t in real_trades if t.pnl is not None)
        return {
            "paper_pnl": paper_pnl,
            "real_pnl": real_pnl,
            "slippage_cost": paper_pnl - real_pnl,
            "difference": real_pnl - paper_pnl,
        }
