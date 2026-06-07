# shared/compliance_checker.py
"""
Pre-trade compliance checker for SEC regulations, PDT rules, and risk limits.
Used by gateway to validate trades before execution.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


@dataclass
class ComplianceResult:
    """Result of a compliance check with full details."""
    passes: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    max_allowed_notional: Optional[float] = None
    pdt_day_trades: int = 0
    short_positions: Dict[str, int] = field(default_factory=dict)

    def __getitem__(self, key: str):
        """Support dict-style access for backward compatibility with tests."""
        return getattr(self, key)


class ComplianceChecker:
    """Validates trades against SEC rules, PDT, and position limits."""

    def __init__(
        self,
        max_position_pct: float = 0.25,
        pdt_min_account_value: float = 25000.0,
    ):
        """
        Initialize compliance checker.

        Args:
            max_position_pct: Maximum position as % of portfolio (default 25%)
            pdt_min_account_value: Minimum account value for PDT ($25k)
        """
        self.max_position_pct = max_position_pct
        self.pdt_min = pdt_min_account_value

    def check_trade(
        self,
        symbol: str,
        quantity: int,
        price: float,
        action: str,  # "BUY" or "SELL"
        portfolio_value: float,
        current_position_qty: int,
        broker_limits: Dict[str, Any],
        day_trades_today: int = 0,
        last_short_price: Optional[float] = None,
    ) -> ComplianceResult:
        """
        Check trade against compliance rules.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            quantity: Number of shares
            price: Price per share
            action: Trade direction ("BUY" or "SELL")
            portfolio_value: Total portfolio value in dollars
            current_position_qty: Current position quantity for this symbol
            broker_limits: Dict of broker-specific limits
            day_trades_today: Count of day trades executed today (0-3+)
            last_short_price: Price at which last short was opened (for short selling)

        Returns:
            ComplianceResult with passes=True if all checks pass, violations list if any fail
        """
        violations = []
        warnings = []

        # Rule 1: Position size limit (25% of portfolio per position)
        notional = quantity * price
        max_allowed = portfolio_value * self.max_position_pct

        if action == "BUY":
            new_position = (current_position_qty + quantity) * price
        else:
            new_position = max(0, current_position_qty - quantity) * price

        if new_position > max_allowed and action == "BUY":
            violations.append("position_limit")
            return ComplianceResult(
                passes=False,
                violations=violations,
                max_allowed_notional=max_allowed,
            )

        # Rule 2: Pattern Day Trader (PDT) rule
        if portfolio_value < self.pdt_min and day_trades_today >= 3:
            # Buying to close or opening a new position would be 4th day trade
            if action == "BUY" or (action == "SELL" and current_position_qty > 0):
                violations.append("pdt_violation")
                return ComplianceResult(
                    passes=False,
                    violations=violations,
                    pdt_day_trades=day_trades_today + 1,
                )

        # Rule 3: Short-sale uptick rule (can't short unless price >= last price)
        if action == "SELL" and current_position_qty == 0:  # Going short
            if last_short_price is not None and price < last_short_price:
                violations.append("short_sale_uptick")
                return ComplianceResult(passes=False, violations=violations)

        # Rule 4: Concentration warning (15% single position limit)
        concentration_pct = new_position / portfolio_value if action == "BUY" else 0
        if concentration_pct > 0.15:
            result_obj = ComplianceResult(passes=True)
            result_obj.warnings = ["concentration_warning"]
            return result_obj

        # If all checks pass
        return ComplianceResult(passes=True)
