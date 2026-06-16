# shared/brokers/hyperliquid.py
"""
Hyperliquid perpetuals DEX broker adapter.

Install:  pip install hyperliquid-python-sdk
Config fields:
  wallet_address  - Ethereum address (0x...)
  private_key     - Ethereum private key for signing orders
  testnet         - bool (default False)
"""
import asyncio
from shared.brokers.base import BrokerAdapter, BrokerFill

try:
    import eth_account
    from hyperliquid.exchange import Exchange
    from hyperliquid.info import Info
    from hyperliquid.utils import constants
    _HL_AVAILABLE = True
except ImportError:
    _HL_AVAILABLE = False
    Exchange = None  # type: ignore
    Info = None  # type: ignore


class HyperliquidAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        self._exchange = None
        self._info = None
        if not _HL_AVAILABLE:
            return
        try:
            account = eth_account.Account.from_key(config["private_key"])
            base_url = (
                constants.TESTNET_API_URL if config.get("testnet") else constants.MAINNET_API_URL
            )
            self._exchange = Exchange(account, base_url)
            self._info = Info(base_url)
        except Exception:
            pass

    async def is_available(self) -> bool:
        if not self._info:
            return False
        wallet = self.config.get("wallet_address", "")
        if not wallet:
            return False
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: self._info.user_state(wallet))
            return True
        except Exception:
            return False

    async def fill(self, trade: dict) -> BrokerFill:
        if not self._exchange:
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error", fill_price=None, fill_qty=None,
                error_msg="hyperliquid-python-sdk not installed or misconfigured",
            )
        try:
            is_buy = trade["action"] in ("long", "buy")
            # Strip exchange suffixes so "BTCUSDT" → "BTC"
            coin = (
                trade["symbol"].upper()
                .replace("USDT", "")
                .replace("-USD", "")
                .replace("-PERP", "")
            )
            qty = float(trade["quantity"])
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, lambda: self._exchange.market_open(coin, is_buy, qty)
            )
            statuses = result.get("response", {}).get("data", {}).get("statuses", [{}])
            filled = statuses[0].get("filled", {})
            fill_price = float(filled["avgPx"]) if filled.get("avgPx") else None
            fill_qty = float(filled["totalSz"]) if filled.get("totalSz") else qty
            error = statuses[0].get("error")
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error" if error else "filled",
                fill_price=fill_price, fill_qty=fill_qty,
                error_msg=error,
            )
        except Exception as exc:
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error", fill_price=None, fill_qty=None,
                error_msg=str(exc),
            )
