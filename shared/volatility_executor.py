# shared/volatility_executor.py
"""
Volatility-aware execution: uses limit orders when VIX > 25,
smart order routing (VWAP for large, market for small).
"""


class VolatilityExecutor:
    def __init__(self, vix_limit_threshold: float = 25.0):
        """
        Args:
            vix_limit_threshold: Use limit orders when VIX exceeds this
        """
        self.vix_limit_threshold = vix_limit_threshold
        self.large_order_qty = 1000.0  # qty threshold for smart routing
        self.large_order_method = "vwap"  # Use VWAP for large orders
        self.small_order_method = "market"  # Use market for small orders

    def get_order_type(self, vix: float, quantity: float) -> str:
        """
        Determine order type based on volatility and size.

        Returns:
            "market", "limit", or "vwap"
        """
        if vix > self.vix_limit_threshold:
            # High volatility: use limit orders
            return "limit"

        # Normal volatility: smart routing by size
        if quantity > self.large_order_qty:
            return self.large_order_method
        else:
            return self.small_order_method

    def calculate_limit_price(
        self,
        current_price: float,
        action: str,
        vix: float,
    ) -> float:
        """
        Calculate limit price based on volatility.
        Higher VIX = wider spread tolerance.

        Args:
            current_price: Current market price
            action: "long" or "short"
            vix: Current VIX level

        Returns:
            Limit price
        """
        # Scale spread by VIX (higher VIX = more tolerance)
        spread_pct = min(vix / 100, 0.05)  # Max 5% spread

        if action == "long":
            # Buying: limit slightly above market
            return current_price * (1 + spread_pct)
        else:
            # Selling: limit slightly below market
            return current_price * (1 - spread_pct)

    def should_use_vwap(self, quantity: float) -> bool:
        """Check if order qualifies for VWAP."""
        return quantity > self.large_order_qty
