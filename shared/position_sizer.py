# shared/position_sizer.py
"""
Position sizing based on account equity.
Scales quantity per broker account size.
"""


class PositionSizer:
    def __init__(self, max_position_pct: float = 5.0):
        """
        Args:
            max_position_pct: Max % of account equity per position (default 5%)
        """
        self.max_position_pct = max_position_pct

    def calculate_qty(
        self,
        signal_qty: float,
        account_equity: float,
        price: float,
    ) -> float:
        """
        Calculate position size based on account equity.

        Args:
            signal_qty: Base quantity from signal (e.g., 100 shares)
            account_equity: Broker account total value
            price: Current price

        Returns:
            Adjusted quantity respecting max % limit
        """
        max_capital = (account_equity * self.max_position_pct) / 100
        max_qty = max_capital / price if price > 0 else 0
        return min(signal_qty, max_qty)

    def scale_qty_by_equity(
        self,
        base_qty: float,
        base_equity: float,
        target_equity: float,
    ) -> float:
        """
        Scale quantity proportionally to equity.

        Example:
            base_qty = 100 (for $100k account)
            base_equity = 100000
            target_equity = 500000
            Returns: 500 shares (proportional scaling)
        """
        if base_equity <= 0:
            return base_qty
        scale_factor = target_equity / base_equity
        return base_qty * scale_factor
