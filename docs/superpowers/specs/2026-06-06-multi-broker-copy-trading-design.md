# Multi-Broker Copy Trading — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Build order:** 3 of 5

---

## Overview

Upgrade the execution agent from single-broker (Capital.com only) to a copy-trading fan-out system. Every trade decision is executed simultaneously across all configured broker accounts. Brokers are defined in a `brokers.yaml` config file — adding a new broker account requires only a new YAML entry, no code changes. The CIO and portfolio manager receive full multi-broker fill data. Fill failures trigger email alerts but do not block other brokers.

---

## Architecture

### Broker adapter interface — `shared/brokers/base.py`

```python
@dataclass
class BrokerFill:
    broker_name: str
    trade_id: int
    status: str          # "filled" | "rejected" | "error"
    fill_price: float | None
    fill_qty: float | None
    error_msg: str | None
    time: datetime

class BrokerAdapter(ABC):
    def __init__(self, name: str, config: dict): ...

    @abstractmethod
    async def fill(self, trade: dict) -> BrokerFill: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
```

### Broker implementations

| File | Broker | Library |
|------|--------|---------|
| `shared/brokers/alpaca.py` | Alpaca Markets | `alpaca-py` (already installed) |
| `shared/brokers/ib.py` | Interactive Brokers | `ib_insync` |
| `shared/brokers/capital_com.py` | Capital.com | existing `CapitalComSession` (refactored in) |

**Alpaca adapter:**
- Uses `alpaca-py` REST client (already in requirements.txt)
- Maps internal `action` field ("long"/"short"/"close") to Alpaca order side
- Paper vs live controlled per-account via `brokers.yaml`
- `is_available()`: pings Alpaca clock endpoint

**IB adapter:**
- Uses `ib_insync` library (async wrapper around TWS socket API)
- Requires TWS or IB Gateway running at configured host:port
- `is_available()`: checks socket connection, returns False silently if TWS is down
- Maps symbols: stocks use exchange="SMART", crypto uses exchange="PAXOS"
- Client ID must be unique per concurrent connection

**Capital.com adapter:**
- Wraps existing `CapitalComSession` — no changes to existing logic
- Extracts into the common `BrokerAdapter` interface

### Broker registry — `shared/brokers/registry.py`

Reads `brokers.yaml` at startup, instantiates the correct adapter for each entry.

```python
class BrokerRegistry:
    def __init__(self, config_path: str = "brokers.yaml"): ...
    def load(self) -> list[BrokerAdapter]: ...
    def get_all(self) -> list[BrokerAdapter]: ...
```

### `brokers.yaml` format

```yaml
brokers:
  - name: alpaca-paper
    type: alpaca
    api_key: ${ALPACA_PAPER_KEY}
    secret_key: ${ALPACA_PAPER_SECRET}
    paper: true
    enabled: true

  - name: alpaca-live
    type: alpaca
    api_key: ${ALPACA_LIVE_KEY}
    secret_key: ${ALPACA_LIVE_SECRET}
    paper: false
    enabled: false   # flip to true when ready for live

  - name: ib-paper
    type: ib
    host: 127.0.0.1
    port: 7497       # 7497=paper, 7496=live
    client_id: 1
    enabled: true

  - name: capital-main
    type: capital_com
    api_key: ${CAPITAL_COM_API_KEY}
    identifier: ${CAPITAL_COM_IDENTIFIER}
    password: ${CAPITAL_COM_PASSWORD}
    base_url: ${CAPITAL_COM_BASE_URL}
    enabled: true
```

Adding a new account = add a new block. All `${VAR}` references resolved from environment.

### Fan-out execution — updated `agents/execution/agent.py`

```python
async def _fan_out(self, trade: dict) -> list[BrokerFill]:
    brokers = self.registry.get_all()
    available = [b for b in brokers if await b.is_available()]

    fills = await asyncio.gather(
        *[b.fill(trade) for b in available],
        return_exceptions=True,
    )
    return [f for f in fills if isinstance(f, BrokerFill)]
```

After fan-out:
1. All fills written to `broker_fills` table (one row per broker per trade)
2. Position accounting uses **median fill price** across successful fills
3. Failed brokers trigger `ops.alert` → email via existing NotificationService
4. Full fill summary published to Redis `trade.multi_fill` channel

### New DB table — `broker_fills`

```sql
CREATE TABLE IF NOT EXISTS broker_fills (
    id              BIGSERIAL,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_id        INTEGER REFERENCES trades(id),
    broker_name     TEXT NOT NULL,
    status          TEXT NOT NULL,   -- filled | rejected | error
    fill_price      DOUBLE PRECISION,
    fill_qty        DOUBLE PRECISION,
    error_msg       TEXT
);
SELECT create_hypertable('broker_fills', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS broker_fills_trade_id ON broker_fills(trade_id);
```

### CIO + PM awareness

**CIO agent** — `run_once()` fetches last 24h from `broker_fills`:
```sql
SELECT broker_name, status, count(*), avg(fill_price)
FROM broker_fills
WHERE time > now() - INTERVAL '24 hours'
GROUP BY broker_name, status
```
This broker performance summary is injected into the LLM prompt and daily brief email.

**Portfolio Manager** — subscribes to `trade.multi_fill` Redis channel. When a multi-fill arrives with a failed broker, PM records it and can reduce conviction on subsequent signals if a broker is consistently failing.

### Gateway — new endpoint

`GET /brokers/status` — returns live availability of all configured brokers (for dashboard Operations tab).

---

## IB-specific requirements

- `pip install ib_insync` added to requirements.txt
- IB Gateway or TWS must be running locally; the adapter checks before each fill
- `IB_HOST`, `IB_PORT`, `IB_CLIENT_ID` env vars (documented in `.env.example`)
- Symbol mapping: `AAPL` → stock SMART USD, `BTCUSDT` → crypto PAXOS USD

---

## Files

### New
- `shared/brokers/__init__.py`
- `shared/brokers/base.py`
- `shared/brokers/alpaca.py`
- `shared/brokers/ib.py`
- `shared/brokers/capital_com.py`
- `shared/brokers/registry.py`
- `brokers.yaml`
- `gateway/routers/brokers.py`
- `tests/shared/test_brokers.py`

### Modified
- `agents/execution/agent.py` — replace single-broker with fan-out
- `agents/cio/agent.py` — fetch broker_fills in run_once()
- `agents/portfolio_mgr/agent.py` — subscribe to trade.multi_fill
- `scripts/setup_db.py` — add broker_fills table
- `requirements.txt` — add ib_insync
- `.env.example` — document IB vars

---

## Tests

- `test_alpaca_adapter_fill_paper_order` — mock alpaca-py, assert BrokerFill returned
- `test_ib_adapter_unavailable_returns_gracefully` — TWS not running, assert no exception
- `test_fan_out_executes_all_available_brokers` — 3 brokers, all available, assert 3 fills
- `test_fan_out_continues_if_one_broker_fails` — 1 broker raises, assert other 2 still fill
- `test_registry_loads_brokers_yaml` — assert correct adapter types instantiated
- `test_median_fill_price_computed_correctly` — 3 fills at different prices, assert median used
- `test_broker_fills_written_to_db` — assert one row per broker after fan-out
