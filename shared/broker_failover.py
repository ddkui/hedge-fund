# shared/broker_failover.py
"""
Broker failover system for reliable multi-broker execution.
Retries failed trades on backup brokers.
"""
from typing import Optional
from shared.brokers.base import BrokerFill


class BrokerFailover:
    def __init__(self, healthy_brokers: list, dead_brokers_check_interval_sec: int = 60):
        """
        Args:
            healthy_brokers: List of (broker_adapter, last_health_check_time)
            dead_brokers_check_interval_sec: How often to retry dead brokers
        """
        self.healthy_brokers = healthy_brokers  # [broker_adapter, ...]
        self.dead_brokers = set()
        self.last_health_check = {}

    async def get_available_brokers(self) -> list:
        """Get all brokers that are currently available."""
        available = []
        for broker in self.healthy_brokers:
            if broker.name in self.dead_brokers:
                continue
            available.append(broker)
        return available

    async def mark_broker_dead(self, broker_name: str) -> None:
        """Mark a broker as dead after repeated failures."""
        self.dead_brokers.add(broker_name)

    async def mark_broker_healthy(self, broker_name: str) -> None:
        """Mark a broker as healthy again (retry after cooldown)."""
        self.dead_brokers.discard(broker_name)

    async def execute_with_failover(
        self, trade: dict, primary_fills: list[BrokerFill]
    ) -> list[BrokerFill]:
        """
        Retry failed trades on backup brokers.

        Returns:
            Updated fill list with retries applied
        """
        failed_fills = [f for f in primary_fills if f.status in ("error", "rejected")]

        if not failed_fills:
            return primary_fills

        available = await self.get_available_brokers()
        if not available:
            return primary_fills

        result = primary_fills.copy()

        for failed_fill in failed_fills:
            # Find a backup broker that hasn't been tried yet
            attempted_brokers = {f.broker_name for f in primary_fills}
            backup = next(
                (b for b in available if b.name not in attempted_brokers),
                None,
            )

            if backup:
                retry_fill = await backup.fill(trade)
                result = [f for f in result if f.broker_name != failed_fill.broker_name]
                result.append(retry_fill)

        return result
