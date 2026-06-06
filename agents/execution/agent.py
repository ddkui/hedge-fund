import asyncio
import statistics
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings
from shared.brokers.registry import BrokerRegistry
from shared.brokers.base import BrokerFill


class ExecutionAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._registry = BrokerRegistry().load()

    async def run_once(self):
        state = await self.bus.get("kill_switch_state")
        if state and state.get("halted"):
            self.logger.info("execution_halted_by_kill_switch")
            return

        pending = await self.db.fetch(
            "SELECT id, symbol, action, quantity, paper, broker, asset_class FROM trades WHERE status = 'pending' ORDER BY time ASC"
        )
        if not pending:
            return

        port_state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        cash = float(port_state["cash"]) if port_state else settings.initial_capital
        positions_value = (float(port_state["total_value"]) - cash) if port_state else 0.0
        peak_value = float(port_state["peak_value"]) if port_state else settings.initial_capital
        open_positions = int(port_state["open_positions"]) if port_state else 0

        for trade in pending:
            fills = await self._fan_out(trade)
            if not fills:
                continue
            fill_price = self._median_fill_price(fills, trade)
            if fill_price is None or fill_price <= 0:
                continue
            cash, positions_value, peak_value, open_positions = await self._apply_fill(
                trade, fill_price, cash, positions_value, peak_value, open_positions
            )
            await self._store_broker_fills(fills)
            await self._alert_failures(trade, fills)
            await self.bus.publish("trade.multi_fill", {
                "trade_id": trade["id"],
                "symbol": trade["symbol"],
                "fills": [
                    {"broker": f.broker_name, "status": f.status,
                     "fill_price": f.fill_price, "error": f.error_msg}
                    for f in fills
                ],
            })

    async def _fan_out(self, trade: dict) -> list[BrokerFill]:
        if trade.get("paper", True) or settings.paper_trading:
            rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                trade["symbol"],
            )
            price = float(rows[0]["close"]) if rows else 0.0
            return [BrokerFill(broker_name="paper", trade_id=trade["id"],
                               status="filled", fill_price=price,
                               fill_qty=float(trade["quantity"]), error_msg=None)]

        brokers = self._registry.get_all()
        available = [b for b in brokers if await b.is_available()]
        if not available:
            self.logger.warning("no_brokers_available", trade_id=trade["id"])
            return []

        results = await asyncio.gather(
            *[b.fill(trade) for b in available],
            return_exceptions=True,
        )
        fills = []
        for r in results:
            if isinstance(r, BrokerFill):
                fills.append(r)
            elif isinstance(r, Exception):
                self.logger.error("broker_fill_exception", error=str(r))
        return fills

    def _median_fill_price(self, fills: list[BrokerFill], trade: dict) -> float | None:
        prices = [f.fill_price for f in fills if f.fill_price is not None and f.fill_price > 0]
        if not prices:
            return None
        return statistics.median(prices)

    async def _store_broker_fills(self, fills: list[BrokerFill]) -> None:
        for fill in fills:
            await self.db.execute(
                "INSERT INTO broker_fills (time, trade_id, broker_name, status, fill_price, fill_qty, error_msg) "
                "VALUES ($1, $2, $3, $4, $5, $6, $7)",
                fill.time, fill.trade_id, fill.broker_name, fill.status,
                fill.fill_price, fill.fill_qty, fill.error_msg,
            )

    async def _alert_failures(self, trade: dict, fills: list[BrokerFill]) -> None:
        failed = [f for f in fills if f.status in ("error", "rejected")]
        for f in failed:
            self.logger.warning("broker_fill_failed", broker=f.broker_name,
                                trade_id=trade["id"], error=f.error_msg)
            await self.bus.publish("ops.alert", {
                "level": "warning",
                "agent": "execution",
                "message": f"Broker {f.broker_name} failed on trade {trade['id']}: {f.error_msg}",
            })

    async def _apply_fill(self, trade, fill_price, cash, positions_value, peak_value, open_positions):
        now = self._now()
        symbol = trade["symbol"]
        quantity = float(trade["quantity"])
        action = trade["action"]
        trade_value = quantity * fill_price
        asset_class = trade.get("asset_class") or (
            "crypto" if trade["symbol"].upper().endswith("USDT") else "equity"
        )

        if action == "close":
            await self.db.execute(
                "UPDATE positions SET exit_price=$1, exit_time=$2, status=$3 WHERE symbol=$4 AND status='open'",
                fill_price, now, "closed", symbol,
            )
            positions_value = max(0.0, positions_value - trade_value)
            cash += trade_value
            open_positions = max(0, open_positions - 1)
        else:
            await self.db.execute(
                "INSERT INTO positions (symbol, asset_class, direction, quantity, entry_price, entry_time) "
                "VALUES ($1,$2,$3,$4,$5,$6)",
                symbol, asset_class, action, quantity, fill_price, now,
            )
            positions_value += trade_value
            cash -= trade_value
            open_positions += 1

        total_value = cash + positions_value
        peak_value = max(peak_value, total_value)

        await self.db.execute(
            "INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions) "
            "VALUES ($1,$2,$3,$4,$5)",
            now, cash, total_value, peak_value, open_positions,
        )
        await self.db.execute(
            "UPDATE trades SET status=$1, price=$2 WHERE id=$3",
            "executed", fill_price, trade["id"],
        )

        await self.bus.publish("trade.executed", {
            "trade_id": trade["id"], "symbol": symbol,
            "action": action, "fill_price": fill_price, "quantity": quantity,
        })
        self.logger.info("trade_executed", symbol=symbol, action=action,
                         fill_price=fill_price, quantity=quantity)
        return cash, positions_value, peak_value, open_positions

    async def _fail_trade(self, trade_id: int, error: str):
        now = self._now()
        await self.db.execute("UPDATE trades SET status=$1 WHERE id=$2", "failed", trade_id)
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) "
            "VALUES ($1,'execution',NULL,'broker_error',$2,'trade_failed')",
            now, error,
        )
