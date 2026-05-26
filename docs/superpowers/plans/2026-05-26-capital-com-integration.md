# Capital.com Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Capital.com as a live CFD broker for execution and streaming price feed, alongside existing Alpaca and Binance adapters.

**Architecture:** `CapitalComSession` (httpx) manages session auth and order placement. `CapitalPriceFeed` polls `/api/v1/markets/{epic}` on a timer and writes mid-prices to the `prices` table. `ExecutionAgent._capital_com_fill()` routes trades tagged `broker='capital_com'` to Capital.com.

**Tech Stack:** httpx (REST), asyncio polling (prices), asyncpg (DB upsert), pytest + unittest.mock (tests)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `shared/config.py` | Modify | Add capital_com_* settings |
| `.env.example` | Modify | Document new env vars |
| `scripts/migrate_add_broker.py` | Create | Add broker + asset_class columns to trades table |
| `shared/capital_com.py` | Create | CapitalComSession + CapitalPriceFeed |
| `tests/shared/test_capital_com.py` | Create | Unit tests for both classes |
| `agents/execution/agent.py` | Modify | Add _capital_com_fill(), update routing + SQL query |
| `tests/agents/execution/test_agent.py` | Modify | Add Capital.com fill tests |
| `agents/capital_feed/__init__.py` | Create | Package marker |
| `agents/capital_feed/agent.py` | Create | Subprocess entry point for CapitalPriceFeed |
| `tests/agents/capital_feed/test_agent.py` | Create | Tests for subprocess entry point |
| `scripts/start_all.py` | Modify | Add capital_feed to AGENTS list |

---

## Task 1: Config + Environment

**Files:**
- Modify: `shared/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Add Capital.com settings to shared/config.py**

Open `shared/config.py`. Add these fields to the `Settings` class, after the `binance_base_url` line:

```python
    capital_com_api_key: str = ""
    capital_com_identifier: str = ""   # your login email / username
    capital_com_password: str = ""
    capital_com_demo: bool = True      # True = demo, False = live account

    capital_com_leverage_forex: int = 10
    capital_com_leverage_indices: int = 5
    capital_com_leverage_commodities: int = 5
    capital_com_leverage_shares: int = 5

    capital_com_watchlist: str = "GOLD,EURUSD,US30,AAPL"

    @computed_field
    @property
    def capital_com_base_url(self) -> str:
        if self.capital_com_demo:
            return "https://demo-api-capital.backend.gbksoft.net"
        return "https://api-capital.backend.gbksoft.net"
```

- [ ] **Step 2: Add env vars to .env.example**

Open `.env.example`. Append at the end:

```
# Capital.com (CFD broker — execution + price feed)
CAPITAL_COM_API_KEY=
CAPITAL_COM_IDENTIFIER=your-email@example.com
CAPITAL_COM_PASSWORD=
CAPITAL_COM_DEMO=true

CAPITAL_COM_LEVERAGE_FOREX=10
CAPITAL_COM_LEVERAGE_INDICES=5
CAPITAL_COM_LEVERAGE_COMMODITIES=5
CAPITAL_COM_LEVERAGE_SHARES=5

CAPITAL_COM_WATCHLIST=GOLD,EURUSD,US30,AAPL
```

- [ ] **Step 3: Verify settings load**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -c "from shared.config import settings; print(settings.capital_com_base_url)"
```

Expected: `https://demo-api-capital.backend.gbksoft.net`

- [ ] **Step 4: Commit**

```powershell
git add shared/config.py .env.example
git commit -m "feat(config): add Capital.com settings"
```

---

## Task 2: DB Migration — Add broker + asset_class to trades

**Files:**
- Create: `scripts/migrate_add_broker.py`

The `trades` table currently has no `broker` or `asset_class` column. The execution agent needs both to route Capital.com trades.

- [ ] **Step 1: Create the migration script**

```python
# scripts/migrate_add_broker.py
"""
One-time migration: add broker and asset_class columns to the trades table.
Safe to run multiple times — uses IF NOT EXISTS logic.
"""
import asyncio
import sys
sys.path.insert(0, ".")
import asyncpg
from shared.config import settings

MIGRATION = """
DO $$ BEGIN
    ALTER TABLE trades ADD COLUMN IF NOT EXISTS broker TEXT NOT NULL DEFAULT 'paper';
    ALTER TABLE trades ADD COLUMN IF NOT EXISTS asset_class TEXT NOT NULL DEFAULT 'equity';
EXCEPTION WHEN others THEN
    RAISE;
END $$;
"""


async def main():
    print("Connecting to TimescaleDB...")
    conn = await asyncpg.connect(settings.db_dsn)
    print("Running migration...")
    await conn.execute(MIGRATION)
    await conn.close()
    print("Migration complete: trades.broker and trades.asset_class added.")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 2: Commit**

```powershell
git add scripts/migrate_add_broker.py
git commit -m "feat(db): migration to add broker and asset_class columns to trades"
```

---

## Task 3: CapitalComSession — Auth + Order Placement

**Files:**
- Create: `shared/capital_com.py`
- Create: `tests/shared/test_capital_com.py`

Capital.com REST auth: POST `/api/v1/session` with `X-CAP-API-KEY` header returns `CST` and `X-SECURITY-TOKEN` response headers. Both are required on all subsequent requests. Tokens expire in 10 min; we refresh at 9 min.

- [ ] **Step 1: Write failing tests**

```python
# tests/shared/test_capital_com.py
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


# ── helpers ───────────────────────────────────────────────────────────────────

def make_session():
    from shared.capital_com import CapitalComSession
    return CapitalComSession(
        base_url="https://demo-api-capital.backend.gbksoft.net",
        api_key="test-key",
        identifier="test@example.com",
        password="test-pass",
    )


def mock_auth_response():
    """httpx.Response mock with CST and X-SECURITY-TOKEN headers."""
    resp = MagicMock()
    resp.status_code = 200
    resp.headers = {"CST": "cst-token", "X-SECURITY-TOKEN": "sec-token"}
    resp.json.return_value = {}
    return resp


def mock_position_response(deal_ref="DEAL123"):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"dealReference": deal_ref}
    return resp


def mock_confirm_response(level=1900.5):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"status": "ACCEPTED", "level": level}
    return resp


# ── session auth ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_auth_creates_tokens():
    session = make_session()
    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_auth_response())
        mock_client_cls.return_value = mock_client

        await session.connect()

    assert session.cst == "cst-token"
    assert session.security_token == "sec-token"


@pytest.mark.asyncio
async def test_session_reauth_on_401():
    """On 401 during place_order, session re-auths and retries."""
    session = make_session()
    session.cst = "old-cst"
    session.security_token = "old-token"

    unauth = MagicMock()
    unauth.status_code = 401
    unauth.json.return_value = {}

    with patch.object(session, "_authenticate", new_callable=AsyncMock) as mock_auth, \
         patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[
            unauth,                              # first attempt → 401
            mock_position_response("REF1"),       # retry after reauth
        ])
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1850.0))
        mock_client_cls.return_value = mock_client

        mock_auth.return_value = None

        price = await session.place_order("GOLD", "BUY", 1.0)

    mock_auth.assert_called_once()
    assert price == 1850.0


@pytest.mark.asyncio
async def test_session_refresh_called_before_expiry():
    """_refresh_loop calls _authenticate before the 9-minute mark."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    call_count = 0

    async def fake_auth():
        nonlocal call_count
        call_count += 1

    session._authenticate = fake_auth

    # Patch asyncio.sleep to skip the 9-minute wait
    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)
        raise asyncio.CancelledError  # stop after first tick

    with patch("shared.capital_com.asyncio.sleep", fake_sleep):
        try:
            await session._refresh_loop()
        except asyncio.CancelledError:
            pass

    assert sleep_calls == [540]   # 9 minutes = 540 seconds
    assert call_count == 1


# ── order placement ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_capital_fill_long_returns_fill_price():
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_position_response("REF1"))
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1900.5))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 2.0)

    assert price == 1900.5


@pytest.mark.asyncio
async def test_capital_fill_short_returns_fill_price():
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=mock_position_response("REF2"))
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1880.0))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "SELL", 1.0)

    assert price == 1880.0


@pytest.mark.asyncio
async def test_capital_fill_retries_on_failure():
    """First place_order call raises, second succeeds."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls, \
         patch("shared.capital_com.asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=[
            Exception("network error"),
            mock_position_response("REF3"),
        ])
        mock_client.get = AsyncMock(return_value=mock_confirm_response(1910.0))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    assert price == 1910.0


@pytest.mark.asyncio
async def test_capital_fill_fails_trade_on_double_failure():
    """Both attempts raise — place_order returns None."""
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls, \
         patch("shared.capital_com.asyncio.sleep", new_callable=AsyncMock):

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))
        mock_client_cls.return_value = mock_client

        price = await session.place_order("GOLD", "BUY", 1.0)

    assert price is None
```

- [ ] **Step 2: Run to verify failure**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/shared/test_capital_com.py -v 2>&1 | Select-Object -Last 15
```

Expected: `ModuleNotFoundError: No module named 'shared.capital_com'`

- [ ] **Step 3: Create shared/capital_com.py with CapitalComSession**

```python
# shared/capital_com.py
"""
Capital.com broker adapter.

CapitalComSession  — REST session (auth, token refresh, order placement)
CapitalPriceFeed   — Polls /api/v1/markets/{epic} and upserts to prices table
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
import httpx
import structlog


class CapitalComSession:
    """
    Manages a Capital.com REST session.

    Auth: POST /api/v1/session → CST + X-SECURITY-TOKEN headers.
    Tokens expire after 10 min; _refresh_loop re-auths every 9 min.
    place_order: POST /api/v1/positions → GET /api/v1/confirms/{ref} → fill price.
    """

    def __init__(self, base_url: str, api_key: str, identifier: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.identifier = identifier
        self.password = password
        self.cst: str = ""
        self.security_token: str = ""
        self.logger = structlog.get_logger()
        self._refresh_task: asyncio.Task | None = None

    def _auth_headers(self) -> dict[str, str]:
        return {
            "X-CAP-API-KEY": self.api_key,
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token,
            "Content-Type": "application/json",
        }

    async def _authenticate(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/session",
                headers={"X-CAP-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"identifier": self.identifier, "password": self.password, "encryptedPassword": False},
            )
            resp.raise_for_status()
            self.cst = resp.headers["CST"]
            self.security_token = resp.headers["X-SECURITY-TOKEN"]
            self.logger.info("capital_com_authenticated")

    async def connect(self) -> None:
        """Authenticate and start the background token-refresh loop."""
        await self._authenticate()
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def disconnect(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _refresh_loop(self) -> None:
        """Re-authenticate every 9 minutes to keep tokens alive."""
        while True:
            await asyncio.sleep(540)  # 9 minutes
            try:
                await self._authenticate()
            except Exception as exc:
                self.logger.error("capital_com_refresh_failed", error=str(exc))

    async def place_order(self, epic: str, direction: str, size: float) -> float | None:
        """
        Place a market CFD order on Capital.com.

        direction: "BUY" or "SELL"
        Returns the fill price (level), or None on unrecoverable failure.
        """
        try:
            return await self._try_place_order(epic, direction, size)
        except Exception as exc:
            self.logger.error("capital_com_order_failed_first_attempt", epic=epic, error=str(exc))
            await asyncio.sleep(2)
            try:
                return await self._try_place_order(epic, direction, size)
            except Exception as exc2:
                self.logger.error("capital_com_order_failed_final", epic=epic, error=str(exc2))
                return None

    async def _try_place_order(self, epic: str, direction: str, size: float) -> float:
        async with httpx.AsyncClient(timeout=10) as client:
            # Place position
            resp = await client.post(
                f"{self.base_url}/api/v1/positions",
                headers=self._auth_headers(),
                json={
                    "epic": epic,
                    "direction": direction,
                    "size": size,
                    "guaranteedStop": False,
                    "trailingStop": False,
                },
            )
            if resp.status_code == 401:
                self.logger.warning("capital_com_401_reauthing")
                await self._authenticate()
                # Retry once after re-auth
                resp = await client.post(
                    f"{self.base_url}/api/v1/positions",
                    headers=self._auth_headers(),
                    json={
                        "epic": epic,
                        "direction": direction,
                        "size": size,
                        "guaranteedStop": False,
                        "trailingStop": False,
                    },
                )
            resp.raise_for_status()
            deal_ref = resp.json()["dealReference"]

            # Confirm to get fill price
            confirm = await client.get(
                f"{self.base_url}/api/v1/confirms/{deal_ref}",
                headers=self._auth_headers(),
            )
            confirm.raise_for_status()
            return float(confirm.json()["level"])
```

- [ ] **Step 4: Run session tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_capital_com.py -v -k "session or fill" 2>&1 | Select-Object -Last 20
```

Expected: `8 passed`

- [ ] **Step 5: Commit**

```powershell
git add shared/capital_com.py tests/shared/test_capital_com.py
git commit -m "feat(capital-com): CapitalComSession — auth, token refresh, order placement"
```

---

## Task 4: CapitalPriceFeed

**Files:**
- Modify: `shared/capital_com.py` (append CapitalPriceFeed class)
- Modify: `tests/shared/test_capital_com.py` (append price feed tests)

`CapitalPriceFeed` polls `/api/v1/markets/{epic}` for bid/ask, computes mid-price, and upserts to the `prices` table. On error it backs off exponentially (1s → 2s → 4s … cap 60s) and resets on success.

- [ ] **Step 1: Append price feed tests to tests/shared/test_capital_com.py**

Append at the end of `tests/shared/test_capital_com.py`:

```python
# ── price feed ────────────────────────────────────────────────────────────────

def mock_market_response(bid=1899.0, ask=1901.0):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "snapshot": {"bid": bid, "offer": ask}
    }
    return resp


@pytest.mark.asyncio
async def test_price_feed_upserts_tick_to_db():
    from shared.capital_com import CapitalPriceFeed
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    db = AsyncMock()

    feed = CapitalPriceFeed(session=session, db=db, epics=["GOLD"], interval_seconds=0)

    with patch("shared.capital_com.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=mock_market_response(1899.0, 1901.0))
        mock_client_cls.return_value = mock_client

        # Run one tick only
        await feed._tick("GOLD")

    db.execute.assert_called_once()
    call_args = db.execute.call_args[0]
    assert "prices" in call_args[0]
    # mid = (1899 + 1901) / 2 = 1900.0
    assert 1900.0 in call_args


@pytest.mark.asyncio
async def test_price_feed_reconnects_on_disconnect():
    """On exception during tick, feed backs off then retries."""
    from shared.capital_com import CapitalPriceFeed
    session = make_session()
    session.cst = "cst"
    session.security_token = "sec"
    db = AsyncMock()
    feed = CapitalPriceFeed(session=session, db=db, epics=["GOLD"], interval_seconds=0)

    call_count = 0

    async def flaky_tick(epic):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("disconnected")
        raise asyncio.CancelledError  # stop after second call

    feed._tick = flaky_tick

    sleep_calls = []

    async def fake_sleep(secs):
        sleep_calls.append(secs)

    with patch("shared.capital_com.asyncio.sleep", fake_sleep):
        try:
            await feed.run()
        except asyncio.CancelledError:
            pass

    # First backoff should be 1 second
    assert sleep_calls[0] == 1


@pytest.mark.asyncio
async def test_leverage_applied_correctly_per_asset_class():
    """_get_leverage returns the right multiplier per asset_class."""
    from shared.capital_com import get_leverage
    from unittest.mock import MagicMock
    mock_settings = MagicMock()
    mock_settings.capital_com_leverage_forex = 10
    mock_settings.capital_com_leverage_indices = 5
    mock_settings.capital_com_leverage_commodities = 5
    mock_settings.capital_com_leverage_shares = 5

    with patch("shared.capital_com.settings", mock_settings):
        assert get_leverage("forex") == 10
        assert get_leverage("indices") == 5
        assert get_leverage("commodities") == 5
        assert get_leverage("shares") == 5
        assert get_leverage("unknown") == 1  # default: no leverage
```

- [ ] **Step 2: Run to verify new tests fail**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_capital_com.py -v -k "feed or leverage" 2>&1 | Select-Object -Last 10
```

Expected: `ImportError` or `AttributeError` (CapitalPriceFeed not yet defined)

- [ ] **Step 3: Append CapitalPriceFeed + get_leverage to shared/capital_com.py**

Append at the end of `shared/capital_com.py`:

```python

from shared.config import settings


def get_leverage(asset_class: str) -> int:
    """Return leverage multiplier for a given asset class."""
    mapping = {
        "forex": settings.capital_com_leverage_forex,
        "indices": settings.capital_com_leverage_indices,
        "commodities": settings.capital_com_leverage_commodities,
        "shares": settings.capital_com_leverage_shares,
    }
    return mapping.get(asset_class.lower(), 1)


class CapitalPriceFeed:
    """
    Polls Capital.com /api/v1/markets/{epic} for each epic in the watchlist
    and upserts the mid-price into the prices table.

    On error: exponential backoff (1s → 2s → 4s … cap 60s), reset on success.
    """

    def __init__(self, session: CapitalComSession, db: Any, epics: list[str], interval_seconds: int = 5):
        self.session = session
        self.db = db
        self.epics = epics
        self.interval_seconds = interval_seconds
        self.logger = structlog.get_logger()

    async def run(self) -> None:
        backoff = 1
        while True:
            try:
                for epic in self.epics:
                    await self._tick(epic)
                backoff = 1  # reset on success
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.error("capital_feed_error", error=str(exc))
                await asyncio.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)

    async def _tick(self, epic: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.session.base_url}/api/v1/markets/{epic}",
                headers=self.session._auth_headers(),
            )
            resp.raise_for_status()
            snap = resp.json()["snapshot"]
            bid = float(snap["bid"])
            ask = float(snap["offer"])
            mid = (bid + ask) / 2.0
            now = datetime.now(timezone.utc)

        await self.db.execute(
            """
            INSERT INTO prices (time, symbol, asset_class, open, high, low, close, volume)
            VALUES ($1, $2, 'cfd', $3, $3, $3, $3, 0)
            ON CONFLICT (time, symbol) DO UPDATE SET close = EXCLUDED.close
            """,
            now, epic, mid,
        )
        self.logger.debug("capital_feed_tick", epic=epic, mid=mid)
```

- [ ] **Step 4: Run all capital_com tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/shared/test_capital_com.py -v 2>&1 | Select-Object -Last 15
```

Expected: `11 passed`

- [ ] **Step 5: Commit**

```powershell
git add shared/capital_com.py tests/shared/test_capital_com.py
git commit -m "feat(capital-com): CapitalPriceFeed — poll prices and upsert to DB"
```

---

## Task 5: ExecutionAgent — Capital.com Fill + Routing

**Files:**
- Modify: `agents/execution/agent.py`
- Modify: `tests/agents/execution/test_agent.py`

Update `_get_fill_price()` to route on `trade["broker"] == "capital_com"`. Update the `SELECT` query to fetch `broker` and `asset_class`. Add `_capital_com_fill()`.

- [ ] **Step 1: Write failing tests**

Append at the end of `tests/agents/execution/test_agent.py`:

```python
@pytest.mark.asyncio
async def test_capital_com_fill_long_calls_place_order():
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"

    trade = {
        "id": 10,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 2.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=1900.5)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price == 1900.5
    mock_session.place_order.assert_called_once_with("GOLD", "BUY", 4.0)  # 2.0 * leverage 2 -> wait, commodities=5 so 2.0*5=10? No — see note below


@pytest.mark.asyncio
async def test_capital_com_fill_close_uses_sell_direction():
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"

    trade = {
        "id": 11,
        "symbol": "EURUSD",
        "action": "close",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "forex",
    }

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=1.0821)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price == 1.0821
    call_args = mock_session.place_order.call_args[0]
    assert call_args[1] == "SELL"


@pytest.mark.asyncio
async def test_capital_com_fill_fails_trade_on_none():
    """When place_order returns None, _fail_trade is called."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"

    trade = {
        "id": 12,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }
    agent.db.execute = AsyncMock()

    mock_session = AsyncMock()
    mock_session.place_order = AsyncMock(return_value=None)

    with patch("agents.execution.agent.settings", mock_settings), \
         patch("agents.execution.agent.CapitalComSession", return_value=mock_session):
        price = await agent._capital_com_fill(trade)

    assert price is None
    fail_calls = [c for c in agent.db.execute.call_args_list if "failed" in str(c)]
    assert len(fail_calls) == 1


@pytest.mark.asyncio
async def test_get_fill_price_routes_capital_com_trade():
    """_get_fill_price routes broker='capital_com' to _capital_com_fill."""
    mock_settings, agent = make_agent(paper=False)
    mock_settings.capital_com_api_key = "key"

    trade = {
        "id": 20,
        "symbol": "GOLD",
        "action": "long",
        "quantity": 1.0,
        "paper": False,
        "broker": "capital_com",
        "asset_class": "commodities",
    }

    with patch("agents.execution.agent.settings", mock_settings), \
         patch.object(agent, "_capital_com_fill", new_callable=AsyncMock, return_value=1900.0) as mock_fill:
        price = await agent._get_fill_price(trade)

    mock_fill.assert_called_once_with(trade)
    assert price == 1900.0
```

**Note on leverage test values:** The test `test_capital_com_fill_long_calls_place_order` asserts `place_order("GOLD", "BUY", 4.0)` — update this to match your actual leverage config. With `CAPITAL_COM_LEVERAGE_COMMODITIES=5` and quantity `2.0`, effective size = `2.0 * 5 = 10.0`. Update the assert to `10.0` before running:

```python
    mock_session.place_order.assert_called_once_with("GOLD", "BUY", 10.0)  # 2.0 qty * 5 leverage
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/execution/test_agent.py -v -k "capital" 2>&1 | Select-Object -Last 10
```

Expected: `AttributeError: 'ExecutionAgent' object has no attribute '_capital_com_fill'`

- [ ] **Step 3: Update agents/execution/agent.py**

**3a.** Add import at top of file (after existing imports):

```python
from shared.capital_com import CapitalComSession, get_leverage
```

**3b.** Update the `pending` query in `run_once()` to include `broker` and `asset_class`:

Replace:
```python
        pending = await self.db.fetch(
            "SELECT id, symbol, action, quantity, paper FROM trades WHERE status = 'pending' ORDER BY time ASC"
        )
```

With:
```python
        pending = await self.db.fetch(
            "SELECT id, symbol, action, quantity, paper, broker, asset_class FROM trades WHERE status = 'pending' ORDER BY time ASC"
        )
```

**3c.** Update `_get_fill_price()` — add Capital.com routing before the USDT/Alpaca routing:

Replace:
```python
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
```

With:
```python
    async def _get_fill_price(self, trade) -> float | None:
        if trade.get("paper", True) or settings.paper_trading:
            rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                trade["symbol"],
            )
            if not rows:
                return None
            return float(rows[0]["close"])

        broker = trade.get("broker", "paper")
        if broker == "capital_com" and settings.capital_com_api_key:
            return await self._capital_com_fill(trade)

        symbol = trade["symbol"]
        if symbol.upper().endswith("USDT"):
            return await self._binance_fill(trade)
        return await self._alpaca_fill(trade)
```

**3d.** Add `_capital_com_fill()` method after `_binance_fill()`:

```python
    async def _capital_com_fill(self, trade) -> float | None:
        from shared.capital_com import CapitalComSession, get_leverage
        direction = "SELL" if trade["action"] in ("close", "short") else "BUY"
        asset_class = trade.get("asset_class", "shares")
        leverage = get_leverage(asset_class)
        effective_size = float(trade["quantity"]) * leverage

        session = CapitalComSession(
            base_url=settings.capital_com_base_url,
            api_key=settings.capital_com_api_key,
            identifier=settings.capital_com_identifier,
            password=settings.capital_com_password,
        )
        try:
            await session.connect()
            price = await session.place_order(trade["symbol"], direction, effective_size)
        finally:
            await session.disconnect()

        if price is None:
            await self._fail_trade(trade["id"], "capital_com place_order returned None")
            return None

        self.logger.info(
            "capital_com_fill",
            symbol=trade["symbol"],
            direction=direction,
            size=effective_size,
            price=price,
        )
        return price
```

- [ ] **Step 4: Run execution tests — expect all PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/execution/test_agent.py -v 2>&1 | Select-Object -Last 15
```

Expected: all tests pass (including the 4 new ones)

- [ ] **Step 5: Commit**

```powershell
git add agents/execution/agent.py tests/agents/execution/test_agent.py
git commit -m "feat(execution): add Capital.com fill routing and _capital_com_fill()"
```

---

## Task 6: Capital Feed Subprocess

**Files:**
- Create: `agents/capital_feed/__init__.py`
- Create: `agents/capital_feed/agent.py`
- Create: `tests/agents/capital_feed/__init__.py`
- Create: `tests/agents/capital_feed/test_agent.py`

- [ ] **Step 1: Write failing test**

```python
# tests/agents/capital_feed/test_agent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_capital_feed_agent_starts_feed():
    """main() creates CapitalPriceFeed and calls run()."""
    mock_settings = MagicMock()
    mock_settings.capital_com_api_key = "key"
    mock_settings.capital_com_identifier = "test@example.com"
    mock_settings.capital_com_password = "pass"
    mock_settings.capital_com_demo = True
    mock_settings.capital_com_base_url = "https://demo-api-capital.backend.gbksoft.net"
    mock_settings.capital_com_watchlist = "GOLD,EURUSD"
    mock_settings.db_dsn = "postgresql://x"

    mock_session = AsyncMock()
    mock_feed = AsyncMock()
    mock_feed.run = AsyncMock(side_effect=asyncio.CancelledError)
    mock_db = AsyncMock()

    with patch("agents.capital_feed.agent.settings", mock_settings), \
         patch("agents.capital_feed.agent.CapitalComSession", return_value=mock_session), \
         patch("agents.capital_feed.agent.CapitalPriceFeed", return_value=mock_feed), \
         patch("agents.capital_feed.agent.Database", return_value=mock_db):
        import asyncio
        try:
            from agents.capital_feed.agent import main
            await main()
        except asyncio.CancelledError:
            pass

    mock_session.connect.assert_called_once()
    mock_feed.run.assert_called_once()


@pytest.mark.asyncio
async def test_capital_feed_agent_exits_if_not_configured():
    """main() exits early when capital_com_api_key is empty."""
    import asyncio
    mock_settings = MagicMock()
    mock_settings.capital_com_api_key = ""

    with patch("agents.capital_feed.agent.settings", mock_settings), \
         patch("agents.capital_feed.agent.CapitalComSession") as mock_session_cls:
        from agents.capital_feed.agent import main
        await main()

    mock_session_cls.assert_not_called()
```

- [ ] **Step 2: Run to verify failure**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/capital_feed/test_agent.py -v 2>&1 | Select-Object -Last 10
```

Expected: `ModuleNotFoundError: No module named 'agents.capital_feed'`

- [ ] **Step 3: Create package files**

Create `agents/capital_feed/__init__.py` (empty):
```python
```

Create `tests/agents/capital_feed/__init__.py` (empty):
```python
```

Create `agents/capital_feed/agent.py`:

```python
# agents/capital_feed/agent.py
"""
Capital.com price feed subprocess.
Polls /api/v1/markets/{epic} for each epic in CAPITAL_COM_WATCHLIST
and upserts mid-prices into the prices table.

Run as: python agents/capital_feed/agent.py
"""
import asyncio
import sys
sys.path.insert(0, ".")

from shared.capital_com import CapitalComSession, CapitalPriceFeed
from shared.config import settings
from shared.db import Database


async def main() -> None:
    if not settings.capital_com_api_key:
        print("CAPITAL_COM_API_KEY not set — price feed disabled.")
        return

    epics = [e.strip() for e in settings.capital_com_watchlist.split(",") if e.strip()]
    print(f"Capital.com price feed starting for epics: {epics}")

    db = Database(settings.db_dsn)
    await db.connect()

    session = CapitalComSession(
        base_url=settings.capital_com_base_url,
        api_key=settings.capital_com_api_key,
        identifier=settings.capital_com_identifier,
        password=settings.capital_com_password,
    )
    await session.connect()

    feed = CapitalPriceFeed(session=session, db=db, epics=epics, interval_seconds=5)
    try:
        await feed.run()
    finally:
        await session.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/capital_feed/test_agent.py -v 2>&1 | Select-Object -Last 10
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```powershell
git add agents/capital_feed/ tests/agents/capital_feed/
git commit -m "feat(capital-feed): Capital.com price feed subprocess"
```

---

## Task 7: Wire start_all.py + Final Integration

**Files:**
- Modify: `scripts/start_all.py`

- [ ] **Step 1: Add capital_feed to start_all.py**

Open `scripts/start_all.py`. Add the capital_feed entry at the end of the AGENTS list:

```python
AGENTS: list[str] = [
    # Phase 2: Data ingest
    "data/ingest/main.py",
    # Phase 3: AI analysis
    "agents/technical/main.py",
    "agents/sentiment/main.py",
    "agents/macro/main.py",
    "agents/research/main.py",
    "agents/aggregator/main.py",
    "agents/portfolio_researcher/main.py",
    # Phase 4a: Quant signal layer
    "agents/quant/momentum/main.py",
    "agents/quant/mean_reversion/main.py",
    "agents/quant/ml_quant/main.py",
    "agents/quant/supervisor/main.py",
    # Phase 4b: Portfolio execution layer
    "agents/portfolio_mgr/main.py",
    "agents/risk/main.py",
    "agents/execution/main.py",
    "agents/cio/main.py",
    "agents/ops/main.py",
    "agents/ops/notifications.py",
    # Capital.com price feed (only active when CAPITAL_COM_API_KEY is set)
    "agents/capital_feed/agent.py",
]
```

- [ ] **Step 2: Run the full test suite**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short 2>&1 | Select-Object -Last 20
```

Expected: **241+ passed, 0 failed** (230 existing + 11 new capital_com + 2 capital_feed tests)

- [ ] **Step 3: Commit**

```powershell
git add scripts/start_all.py
git commit -m "feat(capital-feed): wire capital_feed into start_all.py"
```

- [ ] **Step 4: Push to GitHub**

```powershell
git push origin master
```

---

## Quick-Start: Using Capital.com Live

Once implemented, to go live:

1. Fill in `.env`:
   ```
   CAPITAL_COM_API_KEY=your-key
   CAPITAL_COM_IDENTIFIER=your-email@example.com
   CAPITAL_COM_PASSWORD=your-password
   CAPITAL_COM_DEMO=false
   PAPER_TRADING=false
   ```

2. Run the DB migration:
   ```powershell
   .venv\Scripts\python.exe scripts/migrate_add_broker.py
   ```

3. Agents send trades with `broker='capital_com'` and `asset_class='forex'|'indices'|'commodities'|'shares'`.

4. The execution agent routes those trades to `_capital_com_fill()` automatically.
