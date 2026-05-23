import asyncio
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings


class ExecutionAgent(BaseAgent):
    async def run_once(self):
        pending = await self.db.fetch(
            "SELECT id, symbol, action, quantity, paper FROM trades WHERE status = 'pending' ORDER BY time ASC"
        )
        if not pending:
            return

        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        state_cash = float(state["cash"]) if state else settings.initial_capital
        state_total = float(state["total_value"]) if state else settings.initial_capital
        cash = state_cash
        positions_value = state_total - state_cash
        peak_value = float(state["peak_value"]) if state else settings.initial_capital
        open_positions = int(state["open_positions"]) if state else 0

        for trade in pending:
            fill_price = await self._get_fill_price(trade)
            if fill_price is None:
                continue
            cash, positions_value, peak_value, open_positions = await self._apply_fill(
                trade, fill_price, cash, positions_value, peak_value, open_positions
            )

    async def _get_fill_price(self, trade) -> float | None:
        if trade.get("paper", True) or settings.paper_trading:
            rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                trade["symbol"],
            )
            if not rows:
                return None
            return float(rows[0]["close"])

        symbol = trade["symbol"]
        if symbol.upper().endswith("USDT"):
            return await self._binance_fill(trade)
        return await self._alpaca_fill(trade)

    async def _alpaca_fill(self, trade) -> float | None:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=False)
            side = OrderSide.BUY if trade["action"] == "long" else OrderSide.SELL
            req = MarketOrderRequest(symbol=trade["symbol"], qty=trade["quantity"], side=side, time_in_force=TimeInForce.DAY)
            order = client.submit_order(req)
            return float(order.filled_avg_price) if order.filled_avg_price else None
        except Exception as exc:
            self.logger.error("alpaca_fill_failed", symbol=trade["symbol"], error=str(exc))
            await asyncio.sleep(2)
            try:
                client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=False)
                side = OrderSide.BUY if trade["action"] == "long" else OrderSide.SELL
                req = MarketOrderRequest(symbol=trade["symbol"], qty=trade["quantity"], side=side, time_in_force=TimeInForce.DAY)
                order = client.submit_order(req)
                return float(order.filled_avg_price) if order.filled_avg_price else None
            except Exception as exc2:
                await self._fail_trade(trade["id"], str(exc2))
                return None

    async def _binance_fill(self, trade) -> float | None:
        try:
            from binance.client import Client
            client = Client(settings.binance_api_key, settings.binance_secret_key)
            side = "BUY" if trade["action"] == "long" else "SELL"
            order = client.create_order(symbol=trade["symbol"], side=side, type="MARKET", quantity=trade["quantity"])
            fills = order.get("fills", [])
            return float(fills[0]["price"]) if fills else None
        except Exception as exc:
            self.logger.error("binance_fill_failed", symbol=trade["symbol"], error=str(exc))
            await asyncio.sleep(2)
            try:
                client = Client(settings.binance_api_key, settings.binance_secret_key)
                side = "BUY" if trade["action"] == "long" else "SELL"
                order = client.create_order(symbol=trade["symbol"], side=side, type="MARKET", quantity=trade["quantity"])
                fills = order.get("fills", [])
                return float(fills[0]["price"]) if fills else None
            except Exception as exc2:
                await self._fail_trade(trade["id"], str(exc2))
                return None

    async def _apply_fill(
        self,
        trade,
        fill_price: float,
        cash: float,
        positions_value: float,
        peak_value: float,
        open_positions: int,
    ) -> tuple[float, float, float, int]:
        now = datetime.now(timezone.utc)
        symbol = trade["symbol"]
        quantity = float(trade["quantity"])
        action = trade["action"]
        trade_value = quantity * fill_price
        asset_class = "crypto" if trade["symbol"].upper().endswith("USDT") else "equity"

        if action == "close":
            await self.db.execute(
                "UPDATE positions SET exit_price = $1, exit_time = $2, status = $3 WHERE symbol = $4 AND status = 'open'",
                fill_price, now, "closed", symbol,
            )
            positions_value = max(0.0, positions_value - trade_value)
            cash += trade_value
            open_positions = max(0, open_positions - 1)
        else:
            await self.db.execute(
                "INSERT INTO positions (symbol, asset_class, direction, quantity, entry_price, entry_time) VALUES ($1, $2, $3, $4, $5, $6)",
                symbol, asset_class, action, quantity, fill_price, now,
            )
            positions_value += trade_value
            cash -= trade_value
            open_positions += 1

        total_value = cash + positions_value
        peak_value = max(peak_value, total_value)

        await self.db.execute(
            "INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions) VALUES ($1, $2, $3, $4, $5)",
            now, cash, total_value, peak_value, open_positions,
        )

        await self.db.execute(
            "UPDATE trades SET status = $1, price = $2 WHERE id = $3",
            "executed", fill_price, trade["id"],
        )

        self.logger.info("trade_executed", symbol=symbol, action=action, fill_price=fill_price, quantity=quantity)
        return cash, positions_value, peak_value, open_positions

    async def _fail_trade(self, trade_id: int, error: str):
        now = datetime.now(timezone.utc)
        await self.db.execute("UPDATE trades SET status = $1 WHERE id = $2", "failed", trade_id)
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,'execution',NULL,'broker_error',$2,'trade_failed')",
            now, error,
        )
