# shared/compliance_checker.py
"""
Pre-trade compliance checker for SEC regulations, PDT rules, and risk limits.
Used by gateway to validate trades before execution.
"""
from dataclasses import dataclass
from typing import Optional, Dict


@dataclass
class ComplianceResult:
    """Result of a compliance check with full details."""
    passes: bool
    violations: list[str]
    warnings: list[str] = None
    checked_at: str = None

    def __post_init__(self):
        """Initialize warnings list if not provided."""
        if self.warnings is None:
            self.warnings = []

    def __getitem__(self, key: str):
        """Support dict-style access for backward compatibility with tests."""
        return getattr(self, key)


class ComplianceChecker:
    """Validates trades against SEC rules, PDT, and position limits."""

    def __init__(self):
        pass

    def check_trade(
        self,
        symbol: str,
        action: str,  # "long" or "short"
        quantity: float,
        position_limit_pct: float = 0.05,
        day_trades_today: int = 0,
        last_short_price: Optional[float] = None,
        broker_limits: Optional[Dict] = None,
    ) -> ComplianceResult:
        """
        Check trade against compliance rules.

        Args:
            symbol: Stock symbol (e.g., "AAPL")
            action: Trade direction ("long" or "short")
            quantity: Number of shares
            position_limit_pct: Max position as % of portfolio (default 5%)
            day_trades_today: Count of day trades executed today (0-3+)
            last_short_price: Price at which last short was opened (for short selling)
            broker_limits: Dict of broker-specific limits (reserved for future use)

        Returns:
            ComplianceResult with passes=True if all checks pass, violations list if any fail
        """
        violations = []
        warnings = []

        # 1. Quantity check
        if quantity <= 0:
            violations.append("Quantity must be positive")

        if quantity > 10000:
            violations.append("Quantity exceeds max shares per trade (10000)")

        # 2. Symbol check
        if not symbol or len(symbol) > 5 or not symbol.isupper():
            violations.append("Invalid symbol format")

        # 3. Action check
        if action not in ["long", "short"]:
            violations.append("Action must be 'long' or 'short'")

        # 4. Short selling restrictions (Rule 10a-1)
        if action == "short":
            if last_short_price is None:
                # Simplified check: We need price context for proper uptick rule
                warnings.append("Short sale without previous price reference")
            # Note: Uptick rule enforcement requires real-time tick data

        # 5. Pattern Day Trading rule (PDT)
        if day_trades_today >= 4:
            violations.append(f"PDT rule violated: {day_trades_today} day trades already executed today (limit 3)")

        # 6. Position limit check
        # Note: Actual position sizing relative to portfolio is checked by RiskChecker
        # This just validates the percentage parameter is reasonable
        if position_limit_pct < 0.01 or position_limit_pct > 0.50:
            warnings.append(f"Position limit {position_limit_pct*100}% is unusual (typical: 1-50%)")

        # Prepare result
        passes = len(violations) == 0

        return ComplianceResult(
            passes=passes,
            violations=violations,
            warnings=warnings,
        )

    def check_short_sale(
        self,
        symbol: str,
        quantity: float,
        current_price: float,
        last_short_price: Optional[float] = None,
    ) -> ComplianceResult:
        """
        Check short sale against uptick rule and other short-selling restrictions.

        Args:
            symbol: Stock symbol
            quantity: Shares to short
            current_price: Current market price
            last_short_price: Price at which the last short was executed

        Returns:
            ComplianceResult with violations if uptick rule violated
        """
        violations = []
        warnings = []

        if quantity <= 0:
            violations.append("Short quantity must be positive")

        if symbol and (len(symbol) > 5 or not symbol.isupper()):
            violations.append("Invalid symbol")

        # Uptick rule: short must be at price >= last short price (simplified)
        # In real implementation, would check against last regular sale price
        if last_short_price is not None:
            if current_price < last_short_price * 0.99:  # Allow 1% tolerance
                violations.append(
                    f"Uptick rule: short price {current_price} below last short {last_short_price}"
                )

        passes = len(violations) == 0

        return ComplianceResult(
            passes=passes,
            violations=violations,
            warnings=warnings,
        )

    def check_pdt_status(
        self,
        account_type: str,  # "margin" or "cash"
        equity: float,
        day_trades_count: int,
    ) -> ComplianceResult:
        """
        Check Pattern Day Trader (PDT) status and restrictions.

        Args:
            account_type: "margin" or "cash"
            equity: Current account equity
            day_trades_count: Number of day trades in last 5 trading days

        Returns:
            ComplianceResult with PDT violations
        """
        violations = []
        warnings = []

        if account_type not in ["margin", "cash"]:
            violations.append("Account type must be 'margin' or 'cash'")

        if equity <= 0:
            violations.append("Equity must be positive")

        if day_trades_count < 0:
            violations.append("Day trades count cannot be negative")

        # PDT rule: >= 4 day trades in 5 days requires $25k+ equity on margin account
        if account_type == "margin" and day_trades_count >= 4:
            if equity < 25000:
                violations.append(
                    f"PDT violation: {day_trades_count} day trades but only ${equity} equity (need $25k)"
                )

        passes = len(violations) == 0

        return ComplianceResult(
            passes=passes,
            violations=violations,
            warnings=warnings,
        )
