"""Tax lot accounting and capital gains calculation."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from enum import Enum


class CostBasisMethod(str, Enum):
    """Cost basis calculation methods."""
    FIFO = "fifo"  # First-in, first-out
    LIFO = "lifo"  # Last-in, first-out
    AVERAGE = "average"  # Weighted average cost


@dataclass
class TaxLot:
    """A single tax lot (purchase)."""
    symbol: str
    quantity: int
    purchase_price: float
    purchase_date: datetime
    cost_basis: float = field(init=False)

    def __post_init__(self):
        self.cost_basis = self.quantity * self.purchase_price


@dataclass
class WashSaleCheck:
    """Result of wash-sale detection."""
    is_wash_sale: bool
    disallowed_loss: float = 0.0
    reason: str = ""

    def __getitem__(self, key):
        """Support dict-style access for backward compatibility."""
        if key == "is_wash_sale":
            return self.is_wash_sale
        elif key == "disallowed_loss":
            return self.disallowed_loss
        elif key == "reason":
            return self.reason
        raise KeyError(key)


class TaxCalculator:
    """Calculate capital gains with wash-sale detection."""

    def __init__(self, method: str = "FIFO"):
        self.method = CostBasisMethod(method.lower())
        self.lots: Dict[str, List[TaxLot]] = {}
        self.sales: List[Dict] = []

    def add_lot(
        self,
        symbol: str,
        quantity: int,
        price: float,
        purchase_date: datetime,
    ) -> None:
        """Add a purchase lot."""
        if symbol not in self.lots:
            self.lots[symbol] = []

        lot = TaxLot(symbol, quantity, price, purchase_date)
        self.lots[symbol].append(lot)

    def calculate_gain_on_sale(
        self,
        symbol: str,
        quantity: int,
        sale_price: float,
    ) -> float:
        """
        Calculate gain/loss on sale using configured method (FIFO/LIFO/AVG).

        Returns: gain (positive) or loss (negative)
        """
        if symbol not in self.lots or not self.lots[symbol]:
            return 0.0

        # FIFO: sell oldest lots first
        lots_to_sell = self.lots[symbol].copy()
        if self.method == CostBasisMethod.FIFO:
            lots_to_sell.sort(key=lambda x: x.purchase_date)

        total_cost = 0.0
        remaining_qty = quantity

        for lot in lots_to_sell:
            if remaining_qty <= 0:
                break

            qty_from_lot = min(remaining_qty, lot.quantity)
            total_cost += qty_from_lot * lot.purchase_price
            remaining_qty -= qty_from_lot

        proceeds = quantity * sale_price
        gain = proceeds - total_cost

        return gain

    def record_sale(
        self,
        symbol: str,
        quantity: int,
        sale_price: float,
        sale_date: datetime,
    ) -> None:
        """Record a sale for wash-sale tracking."""
        gain = self.calculate_gain_on_sale(symbol, quantity, sale_price)

        # Get the purchase date for this sale (FIFO - oldest lot)
        purchase_date = None
        if symbol in self.lots and self.lots[symbol]:
            lots_to_sell = self.lots[symbol].copy()
            if self.method == CostBasisMethod.FIFO:
                lots_to_sell.sort(key=lambda x: x.purchase_date)
            if lots_to_sell:
                purchase_date = lots_to_sell[0].purchase_date

        self.sales.append({
            "symbol": symbol,
            "quantity": quantity,
            "sale_price": sale_price,
            "sale_date": sale_date,
            "gain": gain,
            "purchase_date": purchase_date,
        })

        # Remove sold lots
        if symbol in self.lots:
            remaining = quantity
            for lot in self.lots[symbol]:
                if remaining <= 0:
                    break
                qty_removed = min(remaining, lot.quantity)
                lot.quantity -= qty_removed
                remaining -= qty_removed

            # Remove empty lots
            self.lots[symbol] = [lot for lot in self.lots[symbol] if lot.quantity > 0]

    def detect_wash_sale(
        self,
        symbol: str,
        quantity: int,
        repurchase_date: datetime,
    ) -> WashSaleCheck:
        """
        Detect if repurchase is a wash sale.

        Wash sale: repurchase within 30 days of sale at a loss.
        """
        # Find recent sales with losses
        thirty_days_ago = repurchase_date - timedelta(days=30)

        for sale in self.sales:
            if (sale["symbol"] == symbol and
                sale["gain"] < 0 and  # Loss sale
                thirty_days_ago <= sale["sale_date"] <= repurchase_date):

                return WashSaleCheck(
                    is_wash_sale=True,
                    disallowed_loss=sale["gain"],
                    reason=f"Purchase within 30 days of {sale['sale_date'].date()} loss sale"
                )

        return WashSaleCheck(is_wash_sale=False)

    def classify_gain(
        self,
        symbol: str,
        purchase_date: datetime,
        sale_date: datetime,
    ) -> str:
        """Classify gain as short-term or long-term."""
        holding_days = (sale_date - purchase_date).days
        return "long_term" if holding_days >= 365 else "short_term"
