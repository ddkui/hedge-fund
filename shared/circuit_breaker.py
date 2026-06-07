# shared/circuit_breaker.py
"""
Circuit breaker for catastrophic loss protection.
Halts all trading if portfolio drawdown exceeds threshold.
"""
from datetime import datetime, timezone


class CircuitBreaker:
    def __init__(self, max_loss_pct: float = 5.0):
        """
        Args:
            max_loss_pct: Maximum daily loss % before halting (default 5%)
        """
        self.max_loss_pct = max_loss_pct
        self.daily_high = None
        self.tripped = False
        self.tripped_at = None

    def check(self, portfolio_value: float, peak_value: float) -> tuple[bool, str]:
        """
        Check if circuit should trip.

        Returns:
            (is_tripped, reason)
        """
        if self.tripped:
            return True, f"Circuit breaker tripped at {self.tripped_at}. Reset required."

        loss_pct = ((peak_value - portfolio_value) / peak_value) * 100 if peak_value > 0 else 0

        if loss_pct > self.max_loss_pct:
            self.tripped = True
            self.tripped_at = datetime.now(timezone.utc)
            return True, f"Loss {loss_pct:.2f}% exceeds {self.max_loss_pct}% limit"

        return False, f"OK (loss {loss_pct:.2f}%)"

    def reset(self) -> None:
        """Reset circuit breaker for next trading day."""
        self.tripped = False
        self.tripped_at = None

    def is_tripped(self) -> bool:
        """Check if circuit is currently tripped."""
        return self.tripped
