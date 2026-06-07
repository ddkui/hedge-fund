# shared/investor_report.py
"""
Investor monthly reporting - auto-generates PDF reports with P&L, Sharpe, drawdown, etc.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MonthlyMetrics:
    month: str  # "2026-06"
    starting_capital: float
    ending_capital: float
    total_return_pct: float
    monthly_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    win_rate: float
    total_trades: int
    winning_trades: int

    @property
    def profit_loss(self) -> float:
        return self.ending_capital - self.starting_capital


@dataclass
class TopTrade:
    symbol: str
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    quantity: float
    pnl: float
    returns_pct: float


class InvestorReportGenerator:
    def __init__(self, investor_name: str):
        self.investor_name = investor_name
        self.monthly_metrics: list[MonthlyMetrics] = []
        self.top_trades: list[TopTrade] = []
        self.regime_timeline: list[dict] = []

    def add_monthly_metrics(self, metrics: MonthlyMetrics) -> None:
        """Add metrics for a month."""
        self.monthly_metrics.append(metrics)

    def add_top_trades(self, trades: list[TopTrade]) -> None:
        """Add top trades for report."""
        self.top_trades = sorted(trades, key=lambda t: t.pnl, reverse=True)[:5]

    def add_regime_changes(
        self,
        date: datetime,
        regime: str,
        reason: str = "",
    ) -> None:
        """Log regime changes during period."""
        self.regime_timeline.append({
            "date": date,
            "regime": regime,
            "reason": reason,
        })

    def generate_summary(self) -> dict:
        """Generate report summary statistics."""
        if not self.monthly_metrics:
            return {}

        total_return = (
            (self.monthly_metrics[-1].ending_capital -
             self.monthly_metrics[0].starting_capital) /
            self.monthly_metrics[0].starting_capital * 100
        )
        avg_sharpe = sum(m.sharpe_ratio for m in self.monthly_metrics) / len(self.monthly_metrics)
        avg_monthly_return = sum(m.monthly_return_pct for m in self.monthly_metrics) / len(self.monthly_metrics)

        return {
            "investor": self.investor_name,
            "period_return_pct": total_return,
            "avg_monthly_return_pct": avg_monthly_return,
            "avg_sharpe_ratio": avg_sharpe,
            "months_reported": len(self.monthly_metrics),
            "total_trades": sum(m.total_trades for m in self.monthly_metrics),
            "total_winning_trades": sum(m.winning_trades for m in self.monthly_metrics),
        }

    def get_report_data(self) -> dict:
        """Get all data needed for PDF generation."""
        return {
            "investor_name": self.investor_name,
            "generated_date": datetime.now(timezone.utc).isoformat(),
            "monthly_metrics": [
                {
                    "month": m.month,
                    "starting_capital": m.starting_capital,
                    "ending_capital": m.ending_capital,
                    "profit_loss": m.profit_loss,
                    "return_pct": m.monthly_return_pct,
                    "sharpe": m.sharpe_ratio,
                    "max_drawdown": m.max_drawdown_pct,
                    "win_rate": m.win_rate,
                }
                for m in self.monthly_metrics
            ],
            "top_trades": [
                {
                    "symbol": t.symbol,
                    "entry_date": t.entry_date.isoformat(),
                    "exit_date": t.exit_date.isoformat(),
                    "pnl": t.pnl,
                    "returns_pct": t.returns_pct,
                }
                for t in self.top_trades
            ],
            "regime_timeline": self.regime_timeline,
            "summary": self.generate_summary(),
        }
