"""Order clustering: batch small orders to reduce commissions."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any


@dataclass
class ClusteredOrder:
    """A batch of clustered orders."""
    orders: List[Dict[str, Any]]
    total_value: float
    order_count: int
    reason: str = "batch_ready"
    created_at: datetime = field(default_factory=datetime.now)
    execution_time: Optional[datetime] = None


class OrderClusterer:
    """Batches small orders to reduce commission costs."""

    def __init__(
        self,
        min_batch_value: float = 10000.0,
        max_hold_seconds: int = 300,
        commission_per_order: float = 5.0,
        allow_mixed_assets: bool = True,
    ):
        self.min_value = min_batch_value
        self.max_hold = max_hold_seconds
        self.commission = commission_per_order
        self.mixed_assets = allow_mixed_assets
        self.orders: List[Dict[str, Any]] = []

    def add_order(self, order: Dict[str, Any]):
        """Add order to cluster."""
        order["added_at"] = datetime.now()
        self.orders.append(order)

    def get_batch(self) -> Optional[ClusteredOrder]:
        """Get ready batch or None."""
        if not self.orders:
            return None

        total_value = sum(o.get("qty", 0) * o.get("price", 0) for o in self.orders)

        if total_value >= self.min_value:
            return self._create_batch(self.orders, "batch_ready", total_value)

        oldest_order = min(self.orders, key=lambda o: o["added_at"])
        age = (datetime.now() - oldest_order["added_at"]).total_seconds()

        if age > self.max_hold:
            return self._create_batch(self.orders, "timeout", total_value)

        return None

    def _create_batch(
        self,
        orders: List[Dict[str, Any]],
        reason: str,
        total_value: float,
    ) -> ClusteredOrder:
        """Create batch and clear queue."""
        batch = ClusteredOrder(
            orders=orders.copy(),
            total_value=total_value,
            order_count=len(orders),
            reason=reason,
        )
        self.orders = []
        return batch

    def execute_batch(self, batch: ClusteredOrder) -> ClusteredOrder:
        """Mark batch as executed."""
        batch.execution_time = datetime.now()
        return batch

    def calculate_savings(
        self,
        num_orders: int,
        commission_per_order: float,
        batch_commission: float,
    ) -> float:
        """Calculate commission savings from batching."""
        individual_cost = num_orders * commission_per_order
        batch_cost = batch_commission
        return individual_cost - batch_cost
