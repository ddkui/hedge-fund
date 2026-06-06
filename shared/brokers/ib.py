# shared/brokers/ib.py
import asyncio
from shared.brokers.base import BrokerAdapter, BrokerFill

try:
    from ib_insync import IB, MarketOrder, Stock, Crypto
    _IB_AVAILABLE = True
except ImportError:
    _IB_AVAILABLE = False

_CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT"}


class IBAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._host = config.get("host", "127.0.0.1")
        self._port = int(config.get("port", 7497))
        self._client_id = int(config.get("client_id", 1))
        self._ib = IB() if _IB_AVAILABLE else None

    async def _ensure_connected(self) -> bool:
        if not self._ib:
            return False
        if self._ib.isConnected():
            return True
        try:
            await asyncio.wait_for(
                self._ib.connectAsync(self._host, self._port, clientId=self._client_id),
                timeout=5.0,
            )
            return True
        except Exception:
            return False

    async def is_available(self) -> bool:
        return await self._ensure_connected()

    async def fill(self, trade: dict) -> BrokerFill:
        try:
            if not await self._ensure_connected():
                return BrokerFill(broker_name=self.name, trade_id=trade["id"],
                                  status="error", fill_price=None, fill_qty=None,
                                  error_msg="IB Gateway/TWS not reachable")
            symbol = trade["symbol"].replace("USDT", "").replace("USD", "")
            if trade.get("asset_class") == "crypto" or trade["symbol"] in _CRYPTO_SYMBOLS:
                contract = Crypto(symbol, "PAXOS", "USD")
            else:
                contract = Stock(symbol, "SMART", "USD")
            action = "BUY" if trade["action"] == "long" else "SELL"
            order = MarketOrder(action, float(trade["quantity"]))
            trade_obj = self._ib.placeOrder(contract, order)
            for _ in range(20):
                await asyncio.sleep(0.5)
                if trade_obj.orderStatus.status in ("Filled", "Submitted"):
                    break
            avg_price = trade_obj.orderStatus.avgFillPrice or None
            return BrokerFill(broker_name=self.name, trade_id=trade["id"],
                              status="filled" if avg_price else "rejected",
                              fill_price=float(avg_price) if avg_price else None,
                              fill_qty=float(trade["quantity"]), error_msg=None)
        except Exception as exc:
            return BrokerFill(broker_name=self.name, trade_id=trade["id"],
                              status="error", fill_price=None, fill_qty=None, error_msg=str(exc))
