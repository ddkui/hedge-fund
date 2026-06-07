# shared/correlation_hedger.py
"""
Correlation hedging - tracks portfolio correlation to SPY.
Auto-shorts SPY or adds hedges when correlation > 0.8.
"""
from typing import Optional


class CorrelationHedger:
    def __init__(self, correlation_threshold: float = 0.8):
        """
        Args:
            correlation_threshold: Hedge when correlation > this
        """
        self.correlation_threshold = correlation_threshold
        self.current_correlation = 0.0
        self.hedge_active = False
        self.hedge_symbol = "SPY"
        self.hedge_qty = 0.0

    def update_correlation(self, correlation: float) -> None:
        """Update portfolio correlation to SPY."""
        self.current_correlation = correlation

    def should_hedge(self) -> bool:
        """Check if hedge is needed."""
        return self.current_correlation > self.correlation_threshold

    def calculate_hedge_qty(
        self,
        portfolio_value: float,
        spy_price: float,
        hedge_target_pct: float = 10.0,
    ) -> float:
        """
        Calculate SPY short quantity to hedge portfolio.

        Args:
            portfolio_value: Total portfolio value
            spy_price: Current SPY price
            hedge_target_pct: Target hedge as % of portfolio

        Returns:
            Number of SPY shares to short
        """
        hedge_value = (portfolio_value * hedge_target_pct) / 100
        qty = hedge_value / spy_price if spy_price > 0 else 0
        return qty

    def apply_hedge(self, qty: float) -> dict:
        """Apply SPY short hedge."""
        self.hedge_active = True
        self.hedge_qty = qty
        return {
            "hedge_symbol": self.hedge_symbol,
            "action": "short",
            "quantity": qty,
        }

    def remove_hedge(self) -> dict:
        """Close SPY short hedge."""
        self.hedge_active = False
        old_qty = self.hedge_qty
        self.hedge_qty = 0.0
        return {
            "hedge_symbol": self.hedge_symbol,
            "action": "close",
            "quantity": old_qty,
        }

    def is_hedged(self) -> bool:
        """Check if hedge is currently active."""
        return self.hedge_active
