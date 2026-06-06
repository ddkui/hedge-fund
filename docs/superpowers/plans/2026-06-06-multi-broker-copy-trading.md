# Multi-Broker Copy Trading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fan every trade out to all configured broker accounts simultaneously (copy-trading style) using a YAML-driven broker registry. Alpaca and Interactive Brokers are added alongside existing Capital.com. CIO and portfolio manager receive full multi-broker fill data. Failures alert via email but never block other brokers.

**Architecture:** `BrokerAdapter` abstract base class with `fill()` and `is_available()`. Three implementations: Alpaca, IB (ib_insync), Capital.com refactored. `BrokerRegistry` reads `brokers.yaml` at startup. `ExecutionAgent._fan_out()` uses `asyncio.gather()` across all available adapters. Results written to new `broker_fills` table. Median fill price used for position accounting.

**Tech Stack:** Python asyncio, alpaca-py (already installed), ib_insync, FastAPI, TimescaleDB, YAML

---

## File Structure

```
shared/brokers/__init__.py             NEW — package init
shared/brokers/base.py                 NEW — BrokerAdapter ABC + BrokerFill dataclass
shared/brokers/alpaca.py               NEW — Alpaca REST adapter
shared/brokers/ib.py                   NEW — Interactive Brokers adapter (ib_insync)
shared/brokers/capital_com.py          NEW — Capital.com adapter (wraps existing session)
shared/brokers/registry.py             NEW — BrokerRegistry reads brokers.yaml
brokers.yaml                           NEW — broker account config (env vars resolved)
gateway/routers/brokers.py             NEW — GET /brokers/status
agents/execution/agent.py             MODIFY — replace single-broker with fan-out
agents/cio/agent.py                   MODIFY — fetch broker_fills in daily brief
agents/portfolio_mgr/agent.py         MODIFY — subscribe to trade.multi_fill
scripts/setup_db.py                   MODIFY — add broker_fills table
requirements.txt                      MODIFY — add ib_insync
tests/shared/test_brokers.py           NEW
tests/gateway/test_brokers_router.py  NEW
```

---

## Task 1: Broker adapter base + BrokerFill dataclass

**Files:**
- Create: `shared/brokers/__init__.py`
- Create: `shared/brokers/base.py`
- Create: `tests/shared/test_brokers.py` (partial)

- [ ] **Step 1: Create `shared/brokers/__init__.py`**

```python
# shared/brokers/__init__.py
```

- [ ] **Step 2: Create `shared/brokers/base.py`**

```python
# shared/brokers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BrokerFill:
    broker_name: str
    trade_id: int
    status: str               # "filled" | "rejected" | "error"
    fill_price: float | None
    fill_qty: float | None
    error_msg: str | None
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BrokerAdapter(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    async def fill(self, trade: dict) -> BrokerFill:
        """Execute trade and return BrokerFill."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Return True if broker is reachable right now."""
        ...
```

- [ ] **Step 3: Write failing test for base**

```python
# tests/shared/test_brokers.py
import pytest
from datetime import timezone
from shared.brokers.base import BrokerFill, BrokerAdapter


def test_broker_fill_defaults_time():
    fill = BrokerFill(
        broker_name="test", trade_id=1, status="filled",
        fill_price=100.0, fill_qty=10.0, error_msg=None
    )
    assert fill.time.tzinfo is not None
    assert fill.broker_name == "test"
    assert fill.status == "filled"


def test_broker_adapter_is_abstract():
    with pytest.raises(TypeError):
        BrokerAdapter("test", {})  # type: ignore
```

- [ ] **Step 4: Run tests**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/shared/test_brokers.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```powershell
git add shared/brokers/ tests/shared/test_brokers.py
git commit -m "feat(brokers): BrokerAdapter ABC and BrokerFill dataclass"
```

---

## Task 2: Alpaca adapter

**Files:**
- Create: `shared/brokers/alpaca.py`
- Modify: `tests/shared/test_brokers.py`

- [ ] **Step 1: Add Alpaca tests**

Append to `tests/shared/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_alpaca_adapter_fill_returns_broker_fill():
    from unittest.mock import AsyncMock, MagicMock, patch
    with patch("shared.brokers.alpaca.TradingClient") as MockClient:
        mock_client = MagicMock()
        mock_order = MagicMock()
        mock_order.id = "order-123"
        mock_order.filled_avg_price = "185.50"
        mock_order.filled_qty = "10"
        mock_client.submit_order = MagicMock(return_value=mock_order)
        MockClient.return_value = mock_client

        from shared.brokers.alpaca import AlpacaAdapter
        adapter = AlpacaAdapter("alpaca-paper", {
            "api_key": "test-key", "secret_key": "test-secret", "paper": True
        })
        trade = {"id": 1, "symbol": "AAPL", "action": "long",
                 "quantity": 10.0, "asset_class": "stock"}
        fill = await adapter.fill(trade)
        assert fill.status == "filled"
        assert fill.fill_price == 185.50
        assert fill.broker_name == "alpaca-paper"


@pytest.mark.asyncio
async def test_alpaca_adapter_handles_rejection():
    from unittest.mock import MagicMock, patch
    with patch("shared.brokers.alpaca.TradingClient") as MockClient:
        mock_client = MagicMock()
        mock_client.submit_order = MagicMock(side_effect=Exception("insufficient funds"))
        MockClient.return_value = mock_client

        from shared.brokers.alpaca import AlpacaAdapter
        adapter = AlpacaAdapter("alpaca-paper", {
            "api_key": "test-key", "secret_key": "test-secret", "paper": True
        })
        trade = {"id": 1, "symbol": "AAPL", "action": "long",
                 "quantity": 10.0, "asset_class": "stock"}
        fill = await adapter.fill(trade)
        assert fill.status == "error"
        assert "insufficient funds" in fill.error_msg
```

- [ ] **Step 2: Run to verify fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_brokers.py::test_alpaca_adapter_fill_returns_broker_fill -v
```

Expected: `ImportError` (module not created yet)

- [ ] **Step 3: Create `shared/brokers/alpaca.py`**

```python
# shared/brokers/alpaca.py
import asyncio
from shared.brokers.base import BrokerAdapter, BrokerFill

_SIDE_MAP = {"long": "buy", "short": "sell", "close": "sell"}


class AlpacaAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        from alpaca.trading.client import TradingClient
        self._client = TradingClient(
            api_key=config["api_key"],
            secret_key=config["secret_key"],
            paper=config.get("paper", True),
        )

    async def is_available(self) -> bool:
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._client.get_clock)
            return True
        except Exception:
            return False

    async def fill(self, trade: dict) -> BrokerFill:
        try:
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

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
            return BrokerFill(
                broker_name=self.name,
                trade_id=trade["id"],
                status="error",
                fill_price=None,
                fill_qty=None,
                error_msg=str(exc),
            )
```

- [ ] **Step 4: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_brokers.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```powershell
git add shared/brokers/alpaca.py tests/shared/test_brokers.py
git commit -m "feat(brokers): Alpaca adapter with paper/live support"
```

---

## Task 3: IB adapter

**Files:**
- Create: `shared/brokers/ib.py`
- Modify: `requirements.txt`
- Modify: `tests/shared/test_brokers.py`

- [ ] **Step 1: Install ib_insync**

```powershell
.venv\Scripts\pip.exe install ib_insync==0.9.86
```

Add to `requirements.txt`:
```
ib_insync==0.9.86
```

- [ ] **Step 2: Add IB tests**

Append to `tests/shared/test_brokers.py`:

```python
@pytest.mark.asyncio
async def test_ib_adapter_unavailable_when_tws_down():
    from unittest.mock import patch, MagicMock
    with patch("shared.brokers.ib.IB") as MockIB:
        mock_ib = MagicMock()
        mock_ib.isConnected = MagicMock(return_value=False)
        mock_ib.connectAsync = MagicMock(side_effect=ConnectionRefusedError())
        MockIB.return_value = mock_ib

        from shared.brokers.ib import IBAdapter
        adapter = IBAdapter("ib-paper", {"host": "127.0.0.1", "port": 7497, "client_id": 1})
        available = await adapter.is_available()
        assert available is False


@pytest.mark.asyncio
async def test_ib_adapter_fill_returns_error_when_unavailable():
    from unittest.mock import patch, MagicMock
    with patch("shared.brokers.ib.IB") as MockIB:
        mock_ib = MagicMock()
        mock_ib.isConnected = MagicMock(return_value=False)
        MockIB.return_value = mock_ib

        from shared.brokers.ib import IBAdapter
        adapter = IBAdapter("ib-paper", {"host": "127.0.0.1", "port": 7497, "client_id": 1})
        trade = {"id": 1, "symbol": "AAPL", "action": "long",
                 "quantity": 10.0, "asset_class": "stock"}
        fill = await adapter.fill(trade)
        assert fill.status == "error"
        assert fill.broker_name == "ib-paper"
```

- [ ] **Step 3: Create `shared/brokers/ib.py`**

```python
# shared/brokers/ib.py
import asyncio
from shared.brokers.base import BrokerAdapter, BrokerFill

_CRYPTO_SYMBOLS = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}


class IBAdapter(BrokerAdapter):
    def __init__(self, name: str, config: dict):
        super().__init__(name, config)
        from ib_insync import IB
        self._ib = IB()
        self._host = config.get("host", "127.0.0.1")
        self._port = int(config.get("port", 7497))
        self._client_id = int(config.get("client_id", 1))

    async def _ensure_connected(self) -> bool:
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
                return BrokerFill(
                    broker_name=self.name, trade_id=trade["id"],
                    status="error", fill_price=None, fill_qty=None,
                    error_msg="IB Gateway/TWS not reachable",
                )
            from ib_insync import MarketOrder, Stock, Crypto
            symbol = trade["symbol"].replace("USDT", "").replace("USD", "")
            if trade.get("asset_class") == "crypto" or trade["symbol"] in _CRYPTO_SYMBOLS:
                contract = Crypto(symbol, "PAXOS", "USD")
            else:
                contract = Stock(symbol, "SMART", "USD")

            action = "BUY" if trade["action"] == "long" else "SELL"
            order = MarketOrder(action, float(trade["quantity"]))
            trade_obj = self._ib.placeOrder(contract, order)
            # Wait up to 10s for fill
            for _ in range(20):
                await asyncio.sleep(0.5)
                if trade_obj.orderStatus.status in ("Filled", "Submitted"):
                    break
            avg_price = trade_obj.orderStatus.avgFillPrice or None
            return BrokerFill(
                broker_name=self.name,
                trade_id=trade["id"],
                status="filled" if avg_price else "rejected",
                fill_price=float(avg_price) if avg_price else None,
                fill_qty=float(trade["quantity"]),
                error_msg=None,
            )
        except Exception as exc:
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error", fill_price=None, fill_qty=None,
                error_msg=str(exc),
            )
```

- [ ] **Step 4: Run tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_brokers.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```powershell
git add shared/brokers/ib.py requirements.txt tests/shared/test_brokers.py
git commit -m "feat(brokers): Interactive Brokers adapter with graceful TWS unavailability"
```

---

## Task 4: Capital.com adapter + BrokerRegistry

**Files:**
- Create: `shared/brokers/capital_com.py`
- Create: `shared/brokers/registry.py`
- Create: `brokers.yaml`
- Modify: `tests/shared/test_brokers.py`

- [ ] **Step 1: Create `shared/brokers/capital_com.py`**

```python
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
            session = await self._get_session()
            return session is not None
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
            self._session = None  # force re-auth on next call
            return BrokerFill(
                broker_name=self.name, trade_id=trade["id"],
                status="error", fill_price=None, fill_qty=None,
                error_msg=str(exc),
            )
```

- [ ] **Step 2: Create `shared/brokers/registry.py`**

```python
# shared/brokers/registry.py
import os
import re
import yaml
from shared.brokers.base import BrokerAdapter


def _resolve_env(value: str) -> str:
    """Replace ${VAR} with environment variable value."""
    if not isinstance(value, str):
        return value
    return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), value)


def _resolve_dict(d: dict) -> dict:
    return {k: _resolve_env(v) if isinstance(v, str) else v for k, v in d.items()}


class BrokerRegistry:
    def __init__(self, config_path: str = "brokers.yaml"):
        self._config_path = config_path
        self._adapters: list[BrokerAdapter] = []

    def load(self) -> "BrokerRegistry":
        try:
            with open(self._config_path) as f:
                config = yaml.safe_load(f)
        except FileNotFoundError:
            return self
        for entry in config.get("brokers", []):
            if not entry.get("enabled", True):
                continue
            resolved = _resolve_dict(entry)
            broker_type = resolved.get("type")
            name = resolved.get("name", broker_type)
            adapter = self._make_adapter(broker_type, name, resolved)
            if adapter:
                self._adapters.append(adapter)
        return self

    def _make_adapter(self, broker_type: str, name: str, config: dict) -> BrokerAdapter | None:
        if broker_type == "alpaca":
            from shared.brokers.alpaca import AlpacaAdapter
            return AlpacaAdapter(name, config)
        if broker_type == "ib":
            from shared.brokers.ib import IBAdapter
            return IBAdapter(name, config)
        if broker_type == "capital_com":
            from shared.brokers.capital_com import CapitalComAdapter
            return CapitalComAdapter(name, config)
        return None

    def get_all(self) -> list[BrokerAdapter]:
        return self._adapters
```

- [ ] **Step 3: Create `brokers.yaml`**

```yaml
# brokers.yaml
# Add broker accounts here. Each entry is executed simultaneously on every trade.
# Set enabled: false to disable without removing.
# ${VAR} is resolved from environment variables.

brokers:
  - name: capital-main
    type: capital_com
    api_key: ${CAPITAL_COM_API_KEY}
    identifier: ${CAPITAL_COM_IDENTIFIER}
    password: ${CAPITAL_COM_PASSWORD}
    base_url: ${CAPITAL_COM_BASE_URL}
    enabled: true

  - name: alpaca-paper
    type: alpaca
    api_key: ${ALPACA_API_KEY}
    secret_key: ${ALPACA_SECRET_KEY}
    paper: true
    enabled: true

  # Uncomment when IB Gateway/TWS is running:
  # - name: ib-paper
  #   type: ib
  #   host: 127.0.0.1
  #   port: 7497
  #   client_id: 1
  #   enabled: true
```

- [ ] **Step 4: Add registry tests**

Append to `tests/shared/test_brokers.py`:

```python
def test_registry_loads_enabled_brokers(tmp_path):
    yaml_content = """
brokers:
  - name: alpaca-test
    type: alpaca
    api_key: test-key
    secret_key: test-secret
    paper: true
    enabled: true
  - name: disabled-broker
    type: alpaca
    api_key: k
    secret_key: s
    paper: true
    enabled: false
"""
    config_file = tmp_path / "brokers.yaml"
    config_file.write_text(yaml_content)
    from unittest.mock import patch, MagicMock
    with patch("shared.brokers.alpaca.TradingClient"):
        from shared.brokers.registry import BrokerRegistry
        registry = BrokerRegistry(str(config_file)).load()
        brokers = registry.get_all()
        assert len(brokers) == 1
        assert brokers[0].name == "alpaca-test"


def test_registry_empty_when_no_file():
    from shared.brokers.registry import BrokerRegistry
    registry = BrokerRegistry("nonexistent.yaml").load()
    assert registry.get_all() == []
```

- [ ] **Step 5: Run all broker tests**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_brokers.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```powershell
git add shared/brokers/capital_com.py shared/brokers/registry.py brokers.yaml tests/shared/test_brokers.py
git commit -m "feat(brokers): CapitalCom adapter, BrokerRegistry, brokers.yaml config"
```

---

## Task 5: Add broker_fills table

**Files:**
- Modify: `scripts/setup_db.py`

- [ ] **Step 1: Add table to setup_db.py**

In `scripts/setup_db.py`, add inside the `SCHEMA` string before the final `CREATE OR REPLACE FUNCTION`:

```sql
CREATE TABLE IF NOT EXISTS broker_fills (
    id              BIGSERIAL,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id        INTEGER REFERENCES trades(id),
    broker_name     TEXT NOT NULL,
    status          TEXT NOT NULL,
    fill_price      DOUBLE PRECISION,
    fill_qty        DOUBLE PRECISION,
    error_msg       TEXT
);
SELECT create_hypertable('broker_fills', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS broker_fills_trade_id ON broker_fills(trade_id);
CREATE INDEX IF NOT EXISTS broker_fills_broker_time ON broker_fills(broker_name, time DESC);
```

- [ ] **Step 2: Apply migration (requires Docker services running)**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -c "
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from shared.config import settings

SQL = '''
CREATE TABLE IF NOT EXISTS broker_fills (
    id              BIGSERIAL,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id        INTEGER REFERENCES trades(id),
    broker_name     TEXT NOT NULL,
    status          TEXT NOT NULL,
    fill_price      DOUBLE PRECISION,
    fill_qty        DOUBLE PRECISION,
    error_msg       TEXT
);
SELECT create_hypertable(chr(98)||chr(114)||chr(111)||chr(107)||chr(101)||chr(114)||chr(95)||chr(102)||chr(105)||chr(108)||chr(108)||chr(115), chr(116)||chr(105)||chr(109)||chr(101), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS broker_fills_trade_id ON broker_fills(trade_id);
'''

async def main():
    conn = await asyncpg.connect(settings.db_dsn)
    await conn.execute('CREATE TABLE IF NOT EXISTS broker_fills (id BIGSERIAL, time TIMESTAMPTZ NOT NULL DEFAULT NOW(), trade_id INTEGER REFERENCES trades(id), broker_name TEXT NOT NULL, status TEXT NOT NULL, fill_price DOUBLE PRECISION, fill_qty DOUBLE PRECISION, error_msg TEXT)')
    await conn.close()
    print('broker_fills table ready.')

asyncio.run(main())
"
```

- [ ] **Step 3: Commit**

```powershell
git add scripts/setup_db.py
git commit -m "feat(brokers): add broker_fills hypertable to schema"
```

---

## Task 6: Fan-out execution agent

**Files:**
- Modify: `agents/execution/agent.py`

- [ ] **Step 1: Read current execution agent**

Read `agents/execution/agent.py` to understand existing structure before modifying.

- [ ] **Step 2: Update `agents/execution/agent.py`**

Replace the class with fan-out logic. Key changes: load `BrokerRegistry` on init, replace `_get_fill_price` with `_fan_out`, write `broker_fills`, publish `trade.multi_fill`, use median fill price:

```python
# agents/execution/agent.py
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
            "SELECT id, symbol, action, quantity, paper, broker, asset_class "
            "FROM trades WHERE status = 'pending' ORDER BY time ASC"
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
            price_rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                trade["symbol"],
            )
            price = float(price_rows[0]["close"]) if price_rows else 0.0
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

    def _median_fill_price(self, fills: list[BrokerFill], trade: dict) -> float:
        prices = [f.fill_price for f in fills if f.fill_price is not None]
        if not prices:
            return 0.0
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
        """Apply fill to portfolio state. Unchanged from original."""
        now = datetime.now(timezone.utc)
        qty = float(trade["quantity"])
        action = trade["action"]
        symbol = trade["symbol"]

        if action == "long":
            cost = fill_price * qty
            cash -= cost
            positions_value += cost
            open_positions += 1
            await self.db.execute(
                "INSERT INTO positions (symbol, asset_class, direction, quantity, entry_price, entry_time, status) "
                "VALUES ($1, $2, 'long', $3, $4, $5, 'open')",
                symbol, trade.get("asset_class", "stock"), qty, fill_price, now,
            )
        elif action in ("short", "close"):
            proceeds = fill_price * qty
            cash += proceeds
            positions_value -= fill_price * qty
            open_positions = max(0, open_positions - 1)

        total_value = cash + max(positions_value, 0)
        peak_value = max(peak_value, total_value)

        await self.db.execute(
            "INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions) "
            "VALUES ($1, $2, $3, $4, $5)",
            now, cash, total_value, peak_value, open_positions,
        )
        await self.db.execute(
            "UPDATE trades SET status = 'executed' WHERE id = $1", trade["id"]
        )
        await self.bus.publish("trade.executed", {
            "trade_id": trade["id"], "symbol": symbol,
            "action": action, "fill_price": fill_price, "quantity": qty,
        })
        return cash, positions_value, peak_value, open_positions
```

- [ ] **Step 3: Run full test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass

- [ ] **Step 4: Commit**

```powershell
git add agents/execution/agent.py
git commit -m "feat(brokers): fan-out execution across all registry brokers with median fill price"
```

---

## Task 7: CIO + PM awareness + gateway status endpoint

**Files:**
- Modify: `agents/cio/agent.py`
- Create: `gateway/routers/brokers.py`
- Modify: `gateway/main.py`

- [ ] **Step 1: Add broker_fills fetch to CIO agent**

In `agents/cio/agent.py`, add to `run_once()` after the `cio_overrides` fetch:

```python
        # Broker performance (last 24h)
        broker_perf = await self.db.fetch(
            """
            SELECT broker_name, status, count(*) as cnt,
                   avg(fill_price) as avg_price
            FROM broker_fills
            WHERE time > now_or_backtest() - INTERVAL '24 hours'
            GROUP BY broker_name, status
            ORDER BY broker_name, status
            """
        )
        broker_summary = {}
        for row in broker_perf:
            b = row["broker_name"]
            broker_summary.setdefault(b, {})[row["status"]] = {
                "count": row["cnt"], "avg_price": round(float(row["avg_price"] or 0), 4)
            }
```

Add `broker_summary=broker_summary` to the `_build_prompt()` call and `_build_daily_report()` call.

In `_build_prompt()`, add a new section:
```python
        broker_section = f"\n\nBroker performance (last 24h):\n{json.dumps(broker_summary, indent=2)}"
```

Append `broker_section` to the returned prompt string.

In `_build_daily_report()`, add a broker section in the report body (after risk events):
```python
        if broker_summary:
            broker_lines = []
            for broker, statuses in broker_summary.items():
                filled = statuses.get("filled", {}).get("count", 0)
                errors = statuses.get("error", {}).get("count", 0)
                broker_lines.append(f"  • {broker}: {filled} filled, {errors} errors")
            sections += ["", "─" * 60, "BROKER PERFORMANCE", "─" * 60] + broker_lines
```

- [ ] **Step 2: Create `gateway/routers/brokers.py`**

```python
# gateway/routers/brokers.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/status")
async def broker_status(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (broker_name)
            broker_name, status, fill_price, time
        FROM broker_fills
        ORDER BY broker_name, time DESC
        """
    )
    return [dict(r) for r in rows]


@router.get("/fills")
async def broker_fills(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM broker_fills ORDER BY time DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]
```

- [ ] **Step 3: Register in gateway/main.py**

Add import:
```python
from gateway.routers import brokers as brokers_router
```

Add route:
```python
app.include_router(brokers_router.router, prefix="/brokers", tags=["brokers"])
```

- [ ] **Step 4: Run full test suite**

```powershell
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass

- [ ] **Step 5: Commit**

```powershell
git add agents/cio/agent.py gateway/routers/brokers.py gateway/main.py
git commit -m "feat(brokers): CIO broker awareness, /brokers/status gateway endpoint"
```
