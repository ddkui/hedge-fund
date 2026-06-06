# shared/brokers/capital_com.py
from shared.brokers.base import BrokerAdapter, BrokerFill
from shared.capital_com import CapitalComSession


class CapitalComAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._session: CapitalComSession | None = None
        self._config = config

    async def _get_session(self) -> CapitalComSession:
        if self._session is None:
            self._session = CapitalComSession(
                base_url=self._config["base_url"],
                api_key=self._config["api_key"],
                identifier=self._config["identifier"],
                password=self._config["password"],
            )
            await self._session.connect()
        return self._session

    async def is_available(self) -> bool:
        try:
            await self._get_session()
            return True
        except Exception:
            return False

    async def fill(self, trade: dict) -> BrokerFill:
        try:
            session = await self._get_session()
            direction = "BUY" if trade["action"] == "long" else "SELL"
            result = await session.place_order(
                epic=trade["symbol"],
                direction=direction,
                size=float(trade["quantity"]),
            )
            if result.get("dealStatus") == "ACCEPTED":
                return BrokerFill(
                    broker_name=self.name,
                    trade_id=trade["id"],
                    status="filled",
                    fill_price=result.get("level"),
                    fill_qty=float(trade["quantity"]),
                    error_msg=None,
                )
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="rejected", fill_price=None, fill_qty=None,
                error_msg=result.get("reason", "rejected"),
            )
        except Exception as exc:
            self._session = None
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error", fill_price=None, fill_qty=None,
                error_msg=str(exc),
            )
