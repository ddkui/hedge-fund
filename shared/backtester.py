# shared/backtester.py
"""
Backtesting and replay - simulate historical signals against past prices.
Compare paper vs real execution.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
        """Calculate P&L from entry to exit."""
        if self.exit_price is None:
            return None

        pnl = (self.exit_price - self.entry_price) * self.quantity
        if self.action == "short":
            pnl = -pnl  # Reverse sign for short

        self.pnl = pnl
        return pnl

    def calculate_returns_pct(self) -> Optional[float]:
        """Calculate return %."""
        if self.entry_price == 0:
            return None

        returns = ((self.exit_price - self.entry_price) / self.entry_price) * 100
        if self.action == "short":
            returns = -returns

        self.returns_pct = returns
        return returns


class Backtester:
    def __init__(self):
        self.trades: list[BacktestTrade] = []
        self.starting_capital = 100000.0
        self.current_cash = self.starting_capital

    def add_trade(self, trade: BacktestTrade) -> None:
        """Add a trade to backtest."""
        self.trades.append(trade)

    def close_trade(self, symbol: str, exit_price: float) -> None:
        """Close oldest open trade for symbol."""
        open_trades = [
            t for t in self.trades
            if t.symbol == symbol and t.exit_price is None
        ]
        if open_trades:
            open_trades[0].exit_price = exit_price
            open_trades[0].calculate_pnl()
            open_trades[0].calculate_returns_pct()

    def calculate_metrics(self) -> dict:
        """Calculate backtest performance metrics."""
        closed = [t for t in self.trades if t.pnl is not None]
        if not closed:
            return {}

        total_pnl = sum(t.pnl for t in closed)
        winning_trades = len([t for t in closed if t.pnl > 0])
        losing_trades = len([t for t in closed if t.pnl <= 0])
        win_rate = winning_trades / len(closed) if closed else 0

        returns = (total_pnl / self.starting_capital) * 100

        return {
            "total_trades": len(closed),
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "win_rate": win_rate,
            "total_pnl": total_pnl,
            "total_returns_pct": returns,
        }

    def compare_paper_vs_real(
        self,
        paper_trades: list[BacktestTrade],
        real_trades: list[BacktestTrade],
    ) -> dict:
        """Compare paper trading vs real execution."""
        paper_pnl = sum(t.pnl for t in paper_trades if t.pnl is not None)
        real_pnl = sum(t.pnl for t in real_trades if t.pnl is not None)

        return {
            "paper_pnl": paper_pnl,
            "real_pnl": real_pnl,
            "difference": real_pnl - paper_pnl,
            "slippage_pct": ((real_pnl - paper_pnl) / paper_pnl * 100)
            if paper_pnl != 0
            else 0,
        }
