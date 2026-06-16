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
                import pandas as pd
                import numpy as np

                trade_returns = pd.Series([
                    t.pnl / (t.entry_price * t.quantity)
                    if t.entry_price * t.quantity != 0 else 0.0
                    for t in closed
                ])

                def _safe(fn, *args, **kw):
                    try:
                        v = float(fn(*args, **kw))
                        return 0.0 if (np.isnan(v) or np.isinf(v)) else v
                    except Exception:
                        return 0.0

                result.update({
                    "sharpe_ratio": _safe(empyrical.sharpe_ratio, trade_returns),
                    "max_drawdown": _safe(empyrical.max_drawdown, trade_returns),
                    "annual_return": _safe(empyrical.annual_return, trade_returns),
                    "calmar_ratio": _safe(empyrical.calmar_ratio, trade_returns),
                })
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
            "difference": real_pnl - paper_pnl,
            "slippage_pct": ((real_pnl - paper_pnl) / paper_pnl * 100) if paper_pnl != 0 else 0,
        }

    def run(self, prices: "pd.Series", entries: "pd.Series", exits: "pd.Series") -> dict:
        """Vectorised backtest via vectorbt. Returns sharpe, sortino, max_drawdown, win_rate, total_return, calmar_ratio."""
        import vectorbt as vbt
        import numpy as np

        pf = vbt.Portfolio.from_signals(
            close=prices, entries=entries, exits=exits,
            fees=self.fees, slippage=self.slippage, init_cash=self.starting_capital,
        )
        total_return = float(pf.total_return())
        max_dd = float(pf.max_drawdown())
        valid_returns = pf.returns().dropna()
        sharpe = float(pf.sharpe_ratio()) if len(valid_returns) > 1 else 0.0
        def _safe(fn, *args, **kw):
            try:
                v = float(fn(*args, **kw))
                return 0.0 if (np.isnan(v) or np.isinf(v)) else v
            except Exception:
                return 0.0

        try:
            import empyrical
            sortino = _safe(empyrical.sortino_ratio, valid_returns)
            annual_return = _safe(empyrical.annual_return, valid_returns)
        except Exception:
            sortino = 0.0
            annual_return = 0.0
        win_rate = 0.0
        try:
            df = pf.trades.records_readable
            if len(df) > 0:
                col = next((c for c in df.columns if c.lower() == "pnl"), None)
                if col:
                    win_rate = float((df[col] > 0).sum() / len(df))
        except Exception:
            pass
        sharpe = 0.0 if np.isnan(sharpe) else sharpe
        return {
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "max_drawdown": max_dd,
            "win_rate": win_rate,
            "total_return": total_return,
            "annual_return": annual_return,
            "calmar_ratio": total_return / abs(max_dd) if abs(max_dd) > 1e-9 else 0.0,
        }

    def walk_forward(
        self,
        prices: "pd.Series",
        entries: "pd.Series",
        exits: "pd.Series",
        n_splits: int | None = None,
    ) -> "dict | list[dict]":
        """Walk-forward validation.

        n_splits=None: 70/30 in-sample/out-of-sample split → dict.
        n_splits=N:    N equal time windows → list[dict] with per-window metrics.
        """
        if n_splits is not None:
            window = len(prices) // n_splits
            results = []
            for i in range(n_splits):
                s = i * window
                e = s + window if i < n_splits - 1 else len(prices)
                metrics = self.run(prices.iloc[s:e], entries.iloc[s:e], exits.iloc[s:e])
                results.append({"window": i, **metrics})
            return results

        split = int(len(prices) * self.is_ratio)
        return {
            "in_sample": self.run(prices.iloc[:split], entries.iloc[:split], exits.iloc[:split]),
            "out_of_sample": self.run(prices.iloc[split:], entries.iloc[split:], exits.iloc[split:]),
        }


