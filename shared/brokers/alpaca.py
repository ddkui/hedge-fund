# shared/brokers/alpaca.py
import asyncio
from shared.brokers.base import BrokerAdapter, BrokerFill

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    _ALPACA_AVAILABLE = True
except ImportError:
    _ALPACA_AVAILABLE = False


class AlpacaAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        if not _ALPACA_AVAILABLE:
            self._client = None
            return
        self._client = TradingClient(
            api_key=config["api_key"],
            secret_key=config["secret_key"],
            paper=config.get("paper", True),
        )

    async def is_available(self) -> bool:
        if not self._client:
            return False
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.get_clock)
            return True
        except Exception:
            return False

    async def fill(self, trade: dict) -> BrokerFill:
        if not self._client:
            return BrokerFill(broker_name=self.name, trade_id=trade["id"],
                              status="error", fill_price=None, fill_qty=None,
                              error_msg="alpaca-py not installed")
        try:
            side = OrderSide.BUY if trade["action"] == "long" else OrderSide.SELL
            req = MarketOrderRequest(
                symbol=trade["symbol"],
                qty=float(trade["quantity"]),
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            loop = asyncio.get_event_loop()
            order = await loop.run_in_executor(None, self._client.submit_order, req)
            return BrokerFill(
                broker_name=self.name,
                trade_id=trade["id"],
                status="filled",
                fill_price=float(order.filled_avg_price) if order.filled_avg_price else None,
                fill_qty=float(order.filled_qty) if order.filled_qty else float(trade["quantity"]),
                error_msg=None,
            )
        except Exception as exc:
            return BrokerFill(broker_name=self.name, trade_id=trade["id"],
                              status="error", fill_price=None, fill_qty=None,
                              error_msg=str(exc))
