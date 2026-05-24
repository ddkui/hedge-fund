# Phase 5 — Backtesting Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replay the agent pipeline against historical PostgreSQL data to measure strategy performance and produce an interactive HTML report.

**Architecture:** Agent replay — actual `run_once()` code executes against historical data via a PostgreSQL session variable (`backtest.now`) that overrides `NOW()` in all SQL queries. Each run gets an isolated `bt_{run_id}` schema so it never touches live tables. A single `asyncpg.Connection` (not pool) maintains the session variable across all queries per tick.

**Tech Stack:** asyncpg (single connection), pytest-asyncio, plotly (charts), jinja2 (HTML templates)

---

### Task 1: DB Infrastructure

**Files:**
- Create: `scripts/setup_backtest_db.py`
- Modify: `scripts/setup_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backtest/test_infrastructure.py
import pytest
import asyncpg
from unittest.mock import AsyncMock, patch, MagicMock

async def test_setup_backtest_db_runs_schema():
    """setup_backtest_db creates the now_or_backtest function and backtest_runs table."""
    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock()
    mock_conn.close = AsyncMock()

    with patch("asyncpg.connect", return_value=mock_conn) as mock_connect:
        import importlib, sys
        sys.path.insert(0, ".")
        import scripts.setup_backtest_db as sbd
        await sbd.main()

    # Should have called execute at least once with a CREATE TABLE statement
    all_sql = " ".join(call.args[0] for call in mock_conn.execute.call_args_list)
    assert "backtest_runs" in all_sql
    assert "now_or_backtest" in all_sql
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/backtest/test_infrastructure.py::test_setup_backtest_db_runs_schema -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.setup_backtest_db'`

- [ ] **Step 3: Create `scripts/setup_backtest_db.py`**

```python
#!/usr/bin/env python3
"""Creates now_or_backtest() function and backtest_runs table. Run once."""
import asyncio
import asyncpg
import sys
sys.path.insert(0, ".")
from shared.config import settings

SCHEMA = """
CREATE OR REPLACE FUNCTION now_or_backtest()
RETURNS timestamptz AS $$
  SELECT COALESCE(
    NULLIF(current_setting('backtest.now', true), '')::timestamptz,
    NOW()
  )
$$ LANGUAGE SQL STABLE;

CREATE TABLE IF NOT EXISTS backtest_runs (
    id           SERIAL PRIMARY KEY,
    start_date   TIMESTAMPTZ NOT NULL,
    end_date     TIMESTAMPTZ NOT NULL,
    step_seconds INTEGER NOT NULL,
    agents       TEXT[] NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

async def main():
    print("Connecting to TimescaleDB...")
    conn = await asyncpg.connect(settings.db_dsn)
    print("Creating backtest schema objects...")
    await conn.execute(SCHEMA)
    await conn.close()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Add `now_or_backtest()` to `scripts/setup_db.py`**

In `scripts/setup_db.py`, add this block after the last `CREATE INDEX` line, before the closing `"""`:

```python
# Add this at the end of SCHEMA string, before closing """
CREATE OR REPLACE FUNCTION now_or_backtest()
RETURNS timestamptz AS $$
  SELECT COALESCE(
    NULLIF(current_setting('backtest.now', true), '')::timestamptz,
    NOW()
  )
$$ LANGUAGE SQL STABLE;
```

Ensures `now_or_backtest()` exists after a fresh `setup_db.py` run.

- [ ] **Step 5: Run test to verify it passes**

```
pytest tests/backtest/test_infrastructure.py::test_setup_backtest_db_runs_schema -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```
git add scripts/setup_backtest_db.py scripts/setup_db.py tests/backtest/test_infrastructure.py
git commit -m "feat(backtest): add now_or_backtest() function and backtest_runs table"
```

---

### Task 2: `_now()` Refactor — BaseAgent and Agent Files

**Files:**
- Modify: `shared/agent_base.py`
- Modify: `agents/base.py`
- Modify: `agents/portfolio_mgr/agent.py`
- Modify: `agents/execution/agent.py`
- Modify: `agents/risk/agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_now_refactor.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

def _make_agent():
    """Build a minimal AnalysisAgent for testing _now()."""
    import sys; sys.path.insert(0, ".")
    from agents.base import AnalysisAgent

    class DummyAgent(AnalysisAgent):
        async def run_once(self): pass

    mock_db = AsyncMock()
    mock_bus = AsyncMock()
    mock_router = MagicMock()
    return DummyAgent("test_agent", mock_bus, mock_db, mock_router)


async def test_default_now_returns_utc():
    agent = _make_agent()
    result = agent._now()
    assert result.tzinfo is not None
    # Within 2 seconds of now
    diff = abs((datetime.now(timezone.utc) - result).total_seconds())
    assert diff < 2.0


async def test_now_can_be_overridden():
    agent = _make_agent()
    fixed = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    agent._now = lambda: fixed
    assert agent._now() == fixed


async def test_store_signal_uses_now():
    agent = _make_agent()
    fixed = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    agent._now = lambda: fixed

    agent.db.execute = AsyncMock()
    agent.bus.publish = AsyncMock()

    await agent.store_signal("bullish", 0.8, "test reason", symbol="AAPL")

    call_args = agent.db.execute.call_args
    assert call_args[0][1] == fixed  # first positional arg after SQL is 'now'
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_now_refactor.py -v
```
Expected: FAIL — `AttributeError: 'DummyAgent' object has no attribute '_now'`

- [ ] **Step 3: Add `_now()` to `shared/agent_base.py`**

Add import at top (it's already used implicitly — `datetime` needed):

```python
from datetime import datetime, timezone
```

Add method to `BaseAgent` class after `stop()`:

```python
def _now(self) -> datetime:
    return datetime.now(timezone.utc)
```

- [ ] **Step 4: Update `agents/base.py` to use `self._now()`**

Change line 15:
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

- [ ] **Step 5: Update `agents/portfolio_mgr/agent.py`**

In `_write_trade` (line 184):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

In `_log_risk_event` (line 195):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

- [ ] **Step 6: Update `agents/execution/agent.py`**

In `_apply_fill` (line 102):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

In `_fail_trade` (line 143):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

- [ ] **Step 7: Update `agents/risk/agent.py`**

In `_force_close_largest_loser` (line 60):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

In `_log_event` (line 77):
```python
# Before:
now = datetime.now(timezone.utc)
# After:
now = self._now()
```

- [ ] **Step 8: Run tests to verify they pass**

```
pytest tests/backtest/test_now_refactor.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 9: Run full test suite to check for regressions**

```
pytest tests/ -v --tb=short
```
Expected: All previously passing tests still pass.

- [ ] **Step 10: Commit**

```
git add shared/agent_base.py agents/base.py agents/portfolio_mgr/agent.py agents/execution/agent.py agents/risk/agent.py tests/backtest/test_now_refactor.py
git commit -m "feat(backtest): add _now() to BaseAgent for time-overridable timestamps"
```

---

### Task 3: Replace `NOW()` with `now_or_backtest()` in Agent SQL

**Files:**
- Modify: `agents/technical/agent.py`
- Modify: `agents/sentiment/agent.py`
- Modify: `agents/macro/agent.py`
- Modify: `agents/research/agent.py`
- Modify: `agents/aggregator/agent.py`
- Modify: `agents/quant/momentum/agent.py`
- Modify: `agents/quant/mean_reversion/agent.py`
- Modify: `agents/quant/ml_quant/agent.py`
- Modify: `agents/quant/supervisor/agent.py`
- Modify: `agents/portfolio_mgr/agent.py`
- Modify: `agents/risk/checker.py`
- Modify: `agents/risk/agent.py`
- Modify: `agents/cio/agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/backtest/test_sql_now.py
import re
import pytest
from pathlib import Path

AGENT_FILES = [
    "agents/technical/agent.py",
    "agents/sentiment/agent.py",
    "agents/macro/agent.py",
    "agents/research/agent.py",
    "agents/aggregator/agent.py",
    "agents/quant/momentum/agent.py",
    "agents/quant/mean_reversion/agent.py",
    "agents/quant/ml_quant/agent.py",
    "agents/quant/supervisor/agent.py",
    "agents/portfolio_mgr/agent.py",
    "agents/risk/checker.py",
    "agents/risk/agent.py",
    "agents/cio/agent.py",
]

# Pattern: NOW() inside a SQL string (multiline or single-line)
# We look for NOW() that's not inside a Python comment
SQL_NOW_PATTERN = re.compile(r'\bNOW\(\)', re.IGNORECASE)

def test_no_raw_now_in_agent_sql():
    """All agent SQL strings must use now_or_backtest() instead of NOW()."""
    violations = []
    for path in AGENT_FILES:
        content = Path(path).read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if SQL_NOW_PATTERN.search(line):
                violations.append(f"{path}:{i}: {line.strip()}")
    assert not violations, "Raw NOW() found in agent SQL:\n" + "\n".join(violations)
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/backtest/test_sql_now.py -v
```
Expected: FAIL — lists all files containing `NOW()`

- [ ] **Step 3: Replace `NOW()` with `now_or_backtest()` in all 13 files**

Run this Python script (save as `scripts/replace_now.py`, run once, then delete):

```python
#!/usr/bin/env python3
"""One-time script: replace NOW() with now_or_backtest() in agent SQL strings."""
import re
from pathlib import Path

FILES = [
    "agents/technical/agent.py",
    "agents/sentiment/agent.py",
    "agents/macro/agent.py",
    "agents/research/agent.py",
    "agents/aggregator/agent.py",
    "agents/quant/momentum/agent.py",
    "agents/quant/mean_reversion/agent.py",
    "agents/quant/ml_quant/agent.py",
    "agents/quant/supervisor/agent.py",
    "agents/portfolio_mgr/agent.py",
    "agents/risk/checker.py",
    "agents/risk/agent.py",
    "agents/cio/agent.py",
]

pattern = re.compile(r'\bNOW\(\)', re.IGNORECASE)

for filepath in FILES:
    p = Path(filepath)
    original = p.read_text()
    updated = pattern.sub("now_or_backtest()", original)
    if updated != original:
        p.write_text(updated)
        count = len(pattern.findall(original))
        print(f"  {filepath}: replaced {count} occurrence(s)")
    else:
        print(f"  {filepath}: no NOW() found")
```

Run it:
```
python scripts/replace_now.py
```

Expected output: each file listed with replacement count.

- [ ] **Step 4: Run the SQL test to verify it passes**

```
pytest tests/backtest/test_sql_now.py -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v --tb=short
```
Expected: All previously passing tests still pass. The `now_or_backtest()` string change is invisible to mocked DB tests.

- [ ] **Step 6: Delete the one-time script**

```
del scripts\replace_now.py
```

- [ ] **Step 7: Commit**

```
git add agents/technical/agent.py agents/sentiment/agent.py agents/macro/agent.py agents/research/agent.py agents/aggregator/agent.py agents/quant/momentum/agent.py agents/quant/mean_reversion/agent.py agents/quant/ml_quant/agent.py agents/quant/supervisor/agent.py agents/portfolio_mgr/agent.py agents/risk/checker.py agents/risk/agent.py agents/cio/agent.py tests/backtest/test_sql_now.py
git commit -m "feat(backtest): replace NOW() with now_or_backtest() in all agent SQL"
```

---

### Task 4: `BacktestClock`

**Files:**
- Create: `backtest/__init__.py`
- Create: `backtest/clock.py`
- Create: `tests/backtest/__init__.py`
- Create: `tests/backtest/test_clock.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_clock.py
import pytest
from datetime import datetime, timezone, timedelta
from backtest.clock import BacktestClock


def _dt(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


def test_single_tick():
    """Start == end yields exactly one tick."""
    start = _dt(2024, 1, 1)
    clock = BacktestClock(start=start, end=start, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks == [start]


def test_two_ticks():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 1)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks == [start, end]


def test_tick_count_one_day_hourly():
    """One day at 1h step = 25 ticks (00:00 through 24:00)."""
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 2, 0)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert len(ticks) == 25


def test_step_accuracy():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 2)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks[1] - ticks[0] == timedelta(hours=1)


def test_end_boundary_included():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 3)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    ticks = list(clock.ticks())
    assert ticks[-1] == end


def test_len():
    start = _dt(2024, 1, 1, 0)
    end = _dt(2024, 1, 1, 4)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    assert len(clock) == 5


def test_end_before_start_yields_nothing():
    start = _dt(2024, 1, 2)
    end = _dt(2024, 1, 1)
    clock = BacktestClock(start=start, end=end, step_seconds=3600)
    assert list(clock.ticks()) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_clock.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest'`

- [ ] **Step 3: Create `backtest/__init__.py` and `tests/backtest/__init__.py`**

Both files are empty:
```python
# backtest/__init__.py
# (empty)
```
```python
# tests/backtest/__init__.py
# (empty)
```

- [ ] **Step 4: Create `backtest/clock.py`**

```python
from datetime import datetime, timedelta
from typing import Iterator


class BacktestClock:
    def __init__(self, start: datetime, end: datetime, step_seconds: int):
        self.start = start
        self.end = end
        self.step_seconds = step_seconds

    def ticks(self) -> Iterator[datetime]:
        current = self.start
        while current <= self.end:
            yield current
            current += timedelta(seconds=self.step_seconds)

    def __len__(self) -> int:
        if self.end < self.start:
            return 0
        return int((self.end - self.start).total_seconds() / self.step_seconds) + 1
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/backtest/test_clock.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```
git add backtest/__init__.py backtest/clock.py tests/backtest/__init__.py tests/backtest/test_clock.py
git commit -m "feat(backtest): add BacktestClock"
```

---

### Task 5: `InMemoryBus`

**Files:**
- Create: `backtest/bus.py`
- Create: `tests/backtest/test_bus.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_bus.py
import pytest
from backtest.bus import InMemoryBus


async def test_set_and_get_roundtrip():
    bus = InMemoryBus()
    await bus.set("key1", {"value": 42})
    result = await bus.get("key1")
    assert result == {"value": 42}


async def test_get_missing_key_returns_none():
    bus = InMemoryBus()
    result = await bus.get("nonexistent")
    assert result is None


async def test_set_overwrites():
    bus = InMemoryBus()
    await bus.set("k", "first")
    await bus.set("k", "second")
    assert await bus.get("k") == "second"


async def test_ttl_ignored_gracefully():
    """ex= parameter is accepted without error (TTL not enforced in memory)."""
    bus = InMemoryBus()
    await bus.set("k", "v", ex=300)
    assert await bus.get("k") == "v"


async def test_subscribe_yields_nothing():
    bus = InMemoryBus()
    items = []
    async for item in bus.subscribe("channel"):
        items.append(item)
    assert items == []


async def test_publish_is_noop():
    bus = InMemoryBus()
    await bus.publish("chan", {"msg": "hello"})  # must not raise


async def test_connect_disconnect_are_noops():
    bus = InMemoryBus()
    await bus.connect()
    await bus.disconnect()  # must not raise


async def test_bus_state_persists_across_ticks():
    """Directive set at tick 1 is still readable at tick 2."""
    bus = InMemoryBus()
    await bus.set("cio:directive:AAPL", {"action": "avoid_open"})
    # Simulate tick boundary — no clear is called
    result = await bus.get("cio:directive:AAPL")
    assert result == {"action": "avoid_open"}
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_bus.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.bus'`

- [ ] **Step 3: Create `backtest/bus.py`**

```python
from typing import Any, AsyncIterator


class InMemoryBus:
    def __init__(self):
        self._store: dict[str, Any] = {}

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def set(self, key: str, value: Any, ex: int | None = None):
        self._store[key] = value

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def publish(self, channel: str, message: Any):
        pass

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        return
        yield
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/backtest/test_bus.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```
git add backtest/bus.py tests/backtest/test_bus.py
git commit -m "feat(backtest): add InMemoryBus"
```

---

### Task 6: `BacktestDB`

**Files:**
- Create: `backtest/db.py`
- Create: `tests/backtest/test_db.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_db.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock, call


def _make_mock_conn():
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value=None)
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


async def test_connect_sets_search_path():
    mock_conn = _make_mock_conn()
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=42)
        await db.connect()

    # search_path set to bt_42, public
    calls = [str(c) for c in mock_conn.execute.call_args_list]
    assert any("bt_42" in c and "search_path" in c for c in calls)


async def test_set_tick_stores_current_tick():
    mock_conn = _make_mock_conn()
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    dt = datetime(2024, 3, 15, 10, 30, tzinfo=timezone.utc)
    await db.set_tick(dt)

    assert db.current_tick == dt


async def test_set_tick_executes_session_variable():
    mock_conn = _make_mock_conn()
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
    mock_conn.execute.reset_mock()
    await db.set_tick(dt)

    all_sql = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    assert "backtest.now" in all_sql


async def test_fetch_delegates_to_connection():
    mock_conn = _make_mock_conn()
    mock_conn.fetch = AsyncMock(return_value=[{"id": 1}])
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    result = await db.fetch("SELECT 1")
    assert result == [{"id": 1}]


async def test_fetchrow_delegates_to_connection():
    mock_conn = _make_mock_conn()
    mock_conn.fetchrow = AsyncMock(return_value={"cash": 100.0})
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=1)
        await db.connect()

    result = await db.fetchrow("SELECT cash FROM portfolio_state LIMIT 1")
    assert result == {"cash": 100.0}


async def test_create_schema_creates_tables():
    mock_conn = _make_mock_conn()
    with patch("asyncpg.connect", return_value=mock_conn):
        from backtest.db import BacktestDB
        db = BacktestDB(dsn="postgresql://test", run_id=7)
        await db.connect()

    mock_conn.execute.reset_mock()
    await db.create_schema()

    all_sql = " ".join(str(c) for c in mock_conn.execute.call_args_list)
    for table in ("signals", "trades", "positions", "portfolio_state", "risk_events"):
        assert table in all_sql, f"Expected {table} in schema DDL"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_db.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.db'`

- [ ] **Step 3: Create `backtest/db.py`**

```python
import asyncpg
from datetime import datetime


SHADOW_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS signals (
    time        TIMESTAMPTZ NOT NULL,
    agent       TEXT NOT NULL,
    symbol      TEXT,
    signal_type TEXT NOT NULL,
    confidence  DOUBLE PRECISION,
    reasoning   TEXT,
    metadata    JSONB
);

CREATE TABLE IF NOT EXISTS trades (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    action       TEXT NOT NULL,
    symbol       TEXT NOT NULL,
    quantity     DOUBLE PRECISION NOT NULL,
    price        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    paper        BOOLEAN NOT NULL DEFAULT TRUE,
    status       TEXT NOT NULL DEFAULT 'pending',
    pm_reasoning TEXT,
    confidence   DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS positions (
    id          SERIAL PRIMARY KEY,
    symbol      TEXT NOT NULL,
    asset_class TEXT NOT NULL,
    direction   TEXT NOT NULL,
    quantity    DOUBLE PRECISION NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    entry_time  TIMESTAMPTZ NOT NULL,
    entry_thesis TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    exit_price  DOUBLE PRECISION,
    exit_time   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS portfolio_state (
    id             SERIAL PRIMARY KEY,
    time           TIMESTAMPTZ NOT NULL,
    cash           DOUBLE PRECISION NOT NULL,
    total_value    DOUBLE PRECISION NOT NULL,
    peak_value     DOUBLE PRECISION NOT NULL,
    open_positions INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS risk_events (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL,
    agent        TEXT NOT NULL,
    symbol       TEXT,
    limit_type   TEXT NOT NULL,
    details      TEXT NOT NULL,
    action_taken TEXT NOT NULL
);
"""


class BacktestDB:
    def __init__(self, dsn: str, run_id: int):
        self._dsn = dsn
        self._run_id = run_id
        self._schema = f"bt_{run_id}"
        self._conn: asyncpg.Connection | None = None
        self.current_tick: datetime | None = None

    async def connect(self):
        self._conn = await asyncpg.connect(self._dsn)
        await self._conn.execute(
            f"SET search_path = {self._schema}, public"
        )

    async def disconnect(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def create_schema(self):
        await self._conn.execute(f"CREATE SCHEMA IF NOT EXISTS {self._schema}")
        await self._conn.execute(
            f"SET search_path = {self._schema}, public"
        )
        await self._conn.execute(SHADOW_SCHEMA_DDL)

    async def drop_schema(self):
        await self._conn.execute(
            f"DROP SCHEMA IF EXISTS {self._schema} CASCADE"
        )

    async def set_tick(self, dt: datetime):
        self.current_tick = dt
        await self._conn.execute(
            f"SET backtest.now = '{dt.isoformat()}'"
        )

    async def fetch(self, query: str, *args) -> list[dict]:
        rows = await self._conn.fetch(query, *args)
        return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> dict | None:
        row = await self._conn.fetchrow(query, *args)
        return dict(row) if row else None

    async def execute(self, query: str, *args):
        await self._conn.execute(query, *args)
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/backtest/test_db.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```
git add backtest/db.py tests/backtest/test_db.py
git commit -m "feat(backtest): add BacktestDB with schema isolation and session variable"
```

---

### Task 7: `BacktestRunner`

**Files:**
- Create: `backtest/runner.py`
- Create: `tests/backtest/test_runner.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_runner.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch, call


def _dt(hour):
    return datetime(2024, 1, 1, hour, tzinfo=timezone.utc)


def _make_runner(agent_names=None):
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus
    from backtest.runner import BacktestRunner

    clock = BacktestClock(
        start=_dt(0), end=_dt(2), step_seconds=3600
    )

    mock_db = AsyncMock()
    mock_db.current_tick = None
    mock_db.set_tick = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()

    if agent_names is None:
        agent_names = []

    return BacktestRunner(
        run_id=1,
        clock=clock,
        db=mock_db,
        bus=bus,
        agent_names=agent_names,
    ), mock_db


async def test_set_tick_called_per_tick():
    runner, mock_db = _make_runner()
    await runner.run()
    # 3 ticks: 00:00, 01:00, 02:00
    assert mock_db.set_tick.call_count == 3


async def test_portfolio_state_seeded_at_first_tick():
    runner, mock_db = _make_runner()
    await runner.run()

    # First execute call after set_tick should insert initial portfolio_state
    insert_calls = [
        c for c in mock_db.execute.call_args_list
        if "portfolio_state" in str(c) and "INSERT" in str(c)
    ]
    assert len(insert_calls) >= 1


async def test_ticks_advance_in_order():
    runner, mock_db = _make_runner()
    await runner.run()

    tick_calls = [c.args[0] for c in mock_db.set_tick.call_args_list]
    assert tick_calls == [_dt(0), _dt(1), _dt(2)]


async def test_agent_run_once_called_per_tick():
    """Each agent's run_once() is called once per tick."""
    from backtest.runner import BacktestRunner
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus

    mock_db = AsyncMock()
    mock_db.current_tick = _dt(0)
    mock_db.set_tick = AsyncMock(side_effect=lambda dt: setattr(mock_db, 'current_tick', dt))
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()
    clock = BacktestClock(start=_dt(0), end=_dt(1), step_seconds=3600)

    # Patch _build_agents to return a tracked mock agent
    mock_agent = AsyncMock()
    mock_agent.run_once = AsyncMock()
    mock_agent._now = lambda: mock_db.current_tick

    runner = BacktestRunner(
        run_id=1, clock=clock, db=mock_db, bus=bus, agent_names=[]
    )
    runner._tiers = [[mock_agent]]

    await runner.run()

    # 2 ticks → run_once called twice
    assert mock_agent.run_once.call_count == 2


async def test_agent_error_does_not_crash_run():
    """A failing agent should log and continue; the run must complete."""
    from backtest.runner import BacktestRunner
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus

    mock_db = AsyncMock()
    mock_db.current_tick = _dt(0)
    mock_db.set_tick = AsyncMock()
    mock_db.fetchrow = AsyncMock(return_value=None)
    mock_db.execute = AsyncMock()
    mock_db.fetch = AsyncMock(return_value=[])

    bus = InMemoryBus()
    clock = BacktestClock(start=_dt(0), end=_dt(0), step_seconds=3600)

    mock_agent = AsyncMock()
    mock_agent.run_once = AsyncMock(side_effect=RuntimeError("agent exploded"))
    mock_agent._now = lambda: mock_db.current_tick

    runner = BacktestRunner(
        run_id=1, clock=clock, db=mock_db, bus=bus, agent_names=[]
    )
    runner._tiers = [[mock_agent]]

    # Must not raise
    await runner.run()
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_runner.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.runner'`

- [ ] **Step 3: Create `backtest/runner.py`**

```python
import asyncio
import logging
from datetime import datetime, timezone

from backtest.clock import BacktestClock
from backtest.bus import InMemoryBus
from backtest.db import BacktestDB
from shared.config import settings

logger = logging.getLogger("backtest.runner")


class NullRouter:
    """Satisfies agents that call self.router — returns empty string."""
    async def complete(self, *args, **kwargs) -> str:
        return ""

    async def chat(self, *args, **kwargs) -> str:
        return ""


AGENT_TIERS: list[list[str]] = [
    ["technical", "sentiment", "macro", "research"],
    ["aggregator"],
    ["momentum", "mean_reversion", "ml_quant"],
    ["quant_supervisor"],
    ["portfolio_mgr"],
    ["risk"],
    ["execution"],
]

_WATCHLIST = settings.stock_watchlist.split(",") + settings.crypto_watchlist.split(",")


def _build_agent(name: str, db: BacktestDB, bus: InMemoryBus):
    router = NullRouter()
    if name == "technical":
        from agents.technical.agent import TechnicalAnalysisAgent
        return TechnicalAnalysisAgent("technical", bus, db, router, watchlist=_WATCHLIST)
    if name == "sentiment":
        from agents.sentiment.agent import SentimentAgent
        return SentimentAgent("sentiment", bus, db, router)
    if name == "macro":
        from agents.macro.agent import MacroResearchAgent
        return MacroResearchAgent("macro", bus, db, router)
    if name == "research":
        from agents.research.agent import FundamentalResearchAgent
        return FundamentalResearchAgent("research", bus, db, router)
    if name == "aggregator":
        from agents.aggregator.agent import SignalAggregatorAgent
        return SignalAggregatorAgent("aggregator", bus, db, router)
    if name == "momentum":
        from agents.quant.momentum.agent import MomentumQuantAgent
        return MomentumQuantAgent("momentum", bus, db, router, watchlist=_WATCHLIST)
    if name == "mean_reversion":
        from agents.quant.mean_reversion.agent import MeanReversionQuantAgent
        return MeanReversionQuantAgent("mean_reversion", bus, db, router, watchlist=_WATCHLIST)
    if name == "ml_quant":
        from agents.quant.ml_quant.agent import MLQuantAgent
        return MLQuantAgent("ml_quant", bus, db, router, watchlist=_WATCHLIST)
    if name == "quant_supervisor":
        from agents.quant.supervisor.agent import QuantSupervisorAgent
        return QuantSupervisorAgent("quant_supervisor", bus, db, router)
    if name == "portfolio_mgr":
        from agents.portfolio_mgr.agent import PortfolioManagerAgent
        return PortfolioManagerAgent("portfolio_mgr", bus, db, router)
    if name == "risk":
        from agents.risk.agent import RiskAgent
        return RiskAgent("risk", bus, db, router)
    if name == "execution":
        from agents.execution.agent import ExecutionAgent
        return ExecutionAgent("execution", bus, db, router)
    raise ValueError(f"Unknown agent: {name}")


class BacktestRunner:
    def __init__(
        self,
        run_id: int,
        clock: BacktestClock,
        db: BacktestDB,
        bus: InMemoryBus,
        agent_names: list[str],
    ):
        self._run_id = run_id
        self._clock = clock
        self._db = db
        self._bus = bus
        self._tiers = self._build_tiers(agent_names, db, bus)

    def _build_tiers(
        self, agent_names: list[str], db: BacktestDB, bus: InMemoryBus
    ) -> list[list]:
        name_set = set(agent_names)
        tiers = []
        for tier_names in AGENT_TIERS:
            tier = []
            for name in tier_names:
                if name in name_set:
                    agent = _build_agent(name, db, bus)
                    agent._now = lambda: self._db.current_tick
                    tier.append(agent)
            if tier:
                tiers.append(tier)
        return tiers

    async def run(self):
        first_tick = True
        for tick in self._clock.ticks():
            await self._db.set_tick(tick)
            if first_tick:
                await self._seed_portfolio(tick)
                first_tick = False
            for tier in self._tiers:
                for agent in tier:
                    try:
                        await agent.run_once()
                    except Exception as exc:
                        logger.warning(
                            "agent_error",
                            extra={"agent": agent.name, "tick": tick.isoformat(), "error": str(exc)},
                        )

    async def _seed_portfolio(self, tick: datetime):
        await self._db.execute(
            """
            INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions)
            VALUES ($1, $2, $3, $4, $5)
            """,
            tick,
            settings.initial_capital,
            settings.initial_capital,
            settings.initial_capital,
            0,
        )

    async def _fire_tier(self, agents: list):
        for agent in agents:
            try:
                await agent.run_once()
            except Exception as exc:
                logger.warning("agent_error", extra={"agent": getattr(agent, 'name', '?'), "error": str(exc)})
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/backtest/test_runner.py -v
```
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```
git add backtest/runner.py tests/backtest/test_runner.py
git commit -m "feat(backtest): add BacktestRunner with tiered agent execution"
```

---

### Task 8: `compute_metrics`

**Files:**
- Create: `backtest/metrics.py`
- Create: `tests/backtest/test_metrics.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_metrics.py
import pytest
from datetime import datetime, timezone, timedelta
from backtest.metrics import compute_metrics


def _dt(days):
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=days)


def _snap(day, total_value, cash=None):
    v = total_value
    return {
        "time": _dt(day),
        "total_value": v,
        "cash": cash if cash is not None else v,
        "peak_value": v,
    }


def test_total_return_flat():
    snaps = [_snap(0, 100_000), _snap(1, 100_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_return_pct"] == pytest.approx(0.0)


def test_total_return_positive():
    snaps = [_snap(0, 100_000), _snap(365, 120_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_return_pct"] == pytest.approx(20.0)


def test_max_drawdown_none():
    snaps = [_snap(i, 100_000 + i * 1000) for i in range(5)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["max_drawdown_pct"] == pytest.approx(0.0)


def test_max_drawdown_simple():
    """Peak=120k, trough=90k → drawdown = (120k-90k)/120k = 25%."""
    snaps = [
        _snap(0, 100_000),
        _snap(1, 120_000),
        _snap(2, 90_000),
        _snap(3, 100_000),
    ]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["max_drawdown_pct"] == pytest.approx(25.0, abs=0.1)


def test_cagr_one_year_twenty_pct():
    snaps = [_snap(0, 100_000), _snap(365, 120_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["cagr_pct"] == pytest.approx(20.0, abs=0.2)


def test_sharpe_zero_for_flat():
    """All returns = 0 → Sharpe = 0.0."""
    snaps = [_snap(i, 100_000) for i in range(10)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["sharpe_ratio"] == pytest.approx(0.0)


def test_total_trades_count():
    snaps = [_snap(0, 100_000), _snap(1, 105_000)]
    trades = [{"action": "long"}, {"action": "close"}, {"action": "short"}]
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["total_trades"] == 3


def test_final_value():
    snaps = [_snap(0, 100_000), _snap(1, 115_000)]
    trades = []
    m = compute_metrics(snaps, trades, initial_capital=100_000.0)
    assert m["final_value"] == pytest.approx(115_000.0)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_metrics.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.metrics'`

- [ ] **Step 3: Create `backtest/metrics.py`**

```python
import math
from datetime import datetime


def compute_metrics(
    snapshots: list[dict],
    trades: list[dict],
    initial_capital: float,
) -> dict:
    if not snapshots:
        return {
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": len(trades),
            "final_value": initial_capital,
        }

    sorted_snaps = sorted(snapshots, key=lambda s: s["time"])
    values = [float(s["total_value"]) for s in sorted_snaps]
    final_value = values[-1]

    total_return_pct = (final_value - initial_capital) / initial_capital * 100.0

    start_time: datetime = sorted_snaps[0]["time"]
    end_time: datetime = sorted_snaps[-1]["time"]
    years = (end_time - start_time).total_seconds() / (365.25 * 24 * 3600)
    if years > 0 and final_value > 0:
        cagr_pct = ((final_value / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr_pct = total_return_pct

    # Period returns for Sharpe
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            returns.append((values[i] - values[i - 1]) / values[i - 1])

    if returns and any(r != 0 for r in returns):
        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / max(n - 1, 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        if std_r > 0:
            periods_per_year = _estimate_periods_per_year(sorted_snaps)
            sharpe_ratio = (mean_r / std_r) * math.sqrt(periods_per_year)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    # Max drawdown
    peak = values[0]
    max_drawdown_pct = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

    return {
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown_pct,
        "total_trades": len(trades),
        "final_value": final_value,
    }


def _estimate_periods_per_year(snapshots: list[dict]) -> float:
    if len(snapshots) < 2:
        return 252.0
    deltas = []
    for i in range(1, min(10, len(snapshots))):
        dt = (snapshots[i]["time"] - snapshots[i - 1]["time"]).total_seconds()
        if dt > 0:
            deltas.append(dt)
    if not deltas:
        return 252.0
    avg_seconds = sum(deltas) / len(deltas)
    return (365.25 * 24 * 3600) / avg_seconds
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/backtest/test_metrics.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```
git add backtest/metrics.py tests/backtest/test_metrics.py
git commit -m "feat(backtest): add compute_metrics (Sharpe, CAGR, drawdown, win rate)"
```

---

### Task 9: `ReportGenerator` + New Dependencies

**Files:**
- Modify: `requirements.txt`
- Create: `backtest/templates/report.html.j2`
- Create: `backtest/report.py`
- Create: `tests/backtest/test_report.py`

- [ ] **Step 1: Add dependencies to `requirements.txt`**

Append to `requirements.txt`:
```
plotly==5.22.0
jinja2==3.1.4
```

- [ ] **Step 2: Install new dependencies**

```
pip install plotly==5.22.0 jinja2==3.1.4
```
Expected: Both packages install without error.

- [ ] **Step 3: Write the failing tests**

```python
# tests/backtest/test_report.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile


def _dt(days):
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=days)


def _make_report_generator(snapshots, trades):
    from backtest.report import ReportGenerator

    mock_db = AsyncMock()
    mock_db._run_id = 1
    mock_db.fetch = AsyncMock()
    mock_db.fetchrow = AsyncMock()

    # snapshots returned for portfolio_state query
    # trades returned for trades query
    async def fetch_side_effect(query, *args):
        if "portfolio_state" in query:
            return snapshots
        if "trades" in query:
            return trades
        return []

    mock_db.fetch.side_effect = fetch_side_effect
    return ReportGenerator(db=mock_db, run_id=1)


async def test_report_generates_html_file():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
        {"time": _dt(30), "total_value": 110_000.0, "cash": 80_000.0, "peak_value": 110_000.0},
        {"time": _dt(365), "total_value": 120_000.0, "cash": 70_000.0, "peak_value": 120_000.0},
    ]
    trades = [
        {"action": "long", "symbol": "AAPL", "quantity": 10.0, "price": 150.0, "confidence": 75.0, "time": _dt(1)},
    ]
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    assert "<html" in content.lower()
    assert "plotly" in content.lower()


async def test_report_contains_metric_values():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
        {"time": _dt(365), "total_value": 120_000.0, "cash": 70_000.0, "peak_value": 120_000.0},
    ]
    trades = []
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    # 20% total return should appear somewhere
    assert "20" in content


async def test_report_contains_equity_chart_marker():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
    ]
    trades = []
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    assert "equity" in content.lower() or "Equity" in content
```

- [ ] **Step 4: Run tests to verify they fail**

```
pytest tests/backtest/test_report.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.report'`

- [ ] **Step 5: Create `backtest/templates/report.html.j2`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Backtest Report — Run {{ run_id }}</title>
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js"></script>
  <style>
    body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }
    h1, h2 { color: #333; }
    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: right; }
    th { background: #f5f5f5; font-weight: bold; text-align: left; }
    td:first-child { text-align: left; }
    .metric-value { font-weight: bold; }
    .positive { color: #27ae60; }
    .negative { color: #e74c3c; }
    #equity-chart, #drawdown-chart { width: 100%; height: 400px; margin-bottom: 30px; }
  </style>
</head>
<body>
  <h1>Backtest Report</h1>
  <p>Run ID: <strong>{{ run_id }}</strong></p>

  <h2>Key Metrics</h2>
  <table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Total Return</td><td class="metric-value {% if metrics.total_return_pct >= 0 %}positive{% else %}negative{% endif %}">{{ "%.2f"|format(metrics.total_return_pct) }}%</td></tr>
    <tr><td>CAGR</td><td class="metric-value {% if metrics.cagr_pct >= 0 %}positive{% else %}negative{% endif %}">{{ "%.2f"|format(metrics.cagr_pct) }}%</td></tr>
    <tr><td>Sharpe Ratio</td><td class="metric-value">{{ "%.3f"|format(metrics.sharpe_ratio) }}</td></tr>
    <tr><td>Max Drawdown</td><td class="metric-value negative">{{ "%.2f"|format(metrics.max_drawdown_pct) }}%</td></tr>
    <tr><td>Total Trades</td><td class="metric-value">{{ metrics.total_trades }}</td></tr>
    <tr><td>Final Portfolio Value</td><td class="metric-value">${{ "{:,.2f}".format(metrics.final_value) }}</td></tr>
  </table>

  <h2>Equity Curve</h2>
  <div id="equity-chart"></div>

  <h2>Drawdown</h2>
  <div id="drawdown-chart"></div>

  <h2>Trade Log</h2>
  <table>
    <tr>
      <th>Time</th><th>Symbol</th><th>Action</th>
      <th>Quantity</th><th>Price</th><th>Confidence</th>
    </tr>
    {% for t in trades %}
    <tr>
      <td>{{ t.time }}</td>
      <td>{{ t.symbol }}</td>
      <td>{{ t.action }}</td>
      <td>{{ "%.4f"|format(t.quantity|float) }}</td>
      <td>${{ "%.2f"|format(t.price|float) }}</td>
      <td>{{ "%.1f"|format(t.confidence|float) }}%</td>
    </tr>
    {% endfor %}
  </table>

  <script>
    var times = {{ times | tojson }};
    var equity = {{ equity | tojson }};
    var drawdown = {{ drawdown | tojson }};

    Plotly.newPlot('equity-chart', [{
      x: times, y: equity, type: 'scatter', mode: 'lines',
      name: 'Portfolio Value',
      line: {color: '#2ecc71', width: 2}
    }], {
      title: 'Equity Curve',
      xaxis: {title: 'Date'},
      yaxis: {title: 'Portfolio Value ($)', tickformat: '$,.0f'},
      margin: {t: 40}
    });

    Plotly.newPlot('drawdown-chart', [{
      x: times, y: drawdown, type: 'scatter', mode: 'lines',
      name: 'Drawdown %',
      fill: 'tozeroy',
      line: {color: '#e74c3c', width: 2}
    }], {
      title: 'Drawdown',
      xaxis: {title: 'Date'},
      yaxis: {title: 'Drawdown (%)', tickformat: '.1f'},
      margin: {t: 40}
    });
  </script>
</body>
</html>
```

- [ ] **Step 6: Create `backtest/report.py`**

```python
import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from backtest.db import BacktestDB
from backtest.metrics import compute_metrics
from shared.config import settings


class ReportGenerator:
    def __init__(self, db: BacktestDB, run_id: int):
        self._db = db
        self._run_id = run_id
        _templates_dir = Path(__file__).parent / "templates"
        self._env = Environment(loader=FileSystemLoader(str(_templates_dir)))

    async def generate(self, output_path: str) -> dict:
        snapshots = await self._db.fetch(
            "SELECT time, cash, total_value, peak_value FROM portfolio_state ORDER BY time ASC"
        )
        trades = await self._db.fetch(
            "SELECT time, symbol, action, quantity, price, confidence FROM trades ORDER BY time ASC"
        )

        metrics = compute_metrics(snapshots, trades, settings.initial_capital)

        sorted_snaps = sorted(snapshots, key=lambda s: s["time"])
        values = [float(s["total_value"]) for s in sorted_snaps]
        times = [s["time"].isoformat() if hasattr(s["time"], "isoformat") else str(s["time"]) for s in sorted_snaps]

        peak = values[0] if values else 0.0
        drawdown = []
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100.0 if peak > 0 else 0.0
            drawdown.append(round(dd, 4))

        template = self._env.get_template("report.html.j2")
        html = template.render(
            run_id=self._run_id,
            metrics=metrics,
            times=times,
            equity=values,
            drawdown=drawdown,
            trades=trades,
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")
        return metrics
```

- [ ] **Step 7: Run tests to verify they pass**

```
pytest tests/backtest/test_report.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```
git add requirements.txt backtest/templates/report.html.j2 backtest/report.py tests/backtest/test_report.py
git commit -m "feat(backtest): add ReportGenerator with plotly equity curve and jinja2 HTML"
```

---

### Task 10: CLI Entry Point

**Files:**
- Create: `backtest/cli.py`
- Create: `tests/backtest/test_cli.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/backtest/test_cli.py
import pytest
import sys
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone


async def test_cli_parses_start_end():
    """CLI correctly parses --start and --end into aware datetimes."""
    from backtest.cli import parse_args
    args = parse_args([
        "--start", "2024-01-01",
        "--end", "2024-03-31",
        "--step", "1h",
        "--output", "out.html",
    ])
    assert args.start == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert args.end == datetime(2024, 3, 31, tzinfo=timezone.utc)


async def test_cli_parses_step_1h():
    from backtest.cli import parse_step
    assert parse_step("1h") == 3600


async def test_cli_parses_step_30m():
    from backtest.cli import parse_step
    assert parse_step("30m") == 1800


async def test_cli_parses_step_1d():
    from backtest.cli import parse_step
    assert parse_step("1d") == 86400


async def test_cli_parse_step_invalid_raises():
    from backtest.cli import parse_step
    with pytest.raises(ValueError):
        parse_step("2x")


async def test_cli_default_agents():
    """When --agents is omitted, default agent list is used."""
    from backtest.cli import parse_args, DEFAULT_AGENTS
    args = parse_args([
        "--start", "2024-01-01",
        "--end", "2024-01-31",
        "--output", "out.html",
    ])
    assert args.agents == DEFAULT_AGENTS
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/backtest/test_cli.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'backtest.cli'`

- [ ] **Step 3: Create `backtest/cli.py`**

```python
#!/usr/bin/env python3
"""
Backtesting CLI entry point.

Usage:
  python backtest/cli.py \
    --start 2024-01-01 \
    --end   2024-12-31 \
    --step  1h \
    --output reports/backtest_2024.html
"""
import asyncio
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

DEFAULT_AGENTS = [
    "aggregator",
    "momentum", "mean_reversion", "ml_quant",
    "quant_supervisor",
    "portfolio_mgr", "risk", "execution",
]


def parse_step(step_str: str) -> int:
    step_str = step_str.strip().lower()
    if step_str.endswith("h"):
        return int(step_str[:-1]) * 3600
    if step_str.endswith("m"):
        return int(step_str[:-1]) * 60
    if step_str.endswith("d"):
        return int(step_str[:-1]) * 86400
    if step_str.endswith("s"):
        return int(step_str[:-1])
    raise ValueError(f"Unknown step format: {step_str!r}. Use 1h, 30m, 1d, 3600s.")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hedge-fund backtesting engine")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--step", default="1h", help="Clock step e.g. 1h, 30m, 1d")
    parser.add_argument(
        "--agents",
        default=",".join(DEFAULT_AGENTS),
        help="Comma-separated agent names",
    )
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--keep-schema", action="store_true", help="Don't drop bt_N schema after run")

    args = parser.parse_args(argv)
    args.start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    args.end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    args.step_seconds = parse_step(args.step)
    if isinstance(args.agents, str):
        args.agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    return args


async def _main(argv=None):
    import asyncpg
    from shared.config import settings
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus
    from backtest.db import BacktestDB
    from backtest.runner import BacktestRunner
    from backtest.report import ReportGenerator

    args = parse_args(argv)

    # Create backtest_runs entry
    conn = await asyncpg.connect(settings.db_dsn)
    run_id = await conn.fetchval(
        """
        INSERT INTO backtest_runs (start_date, end_date, step_seconds, agents, status)
        VALUES ($1, $2, $3, $4, 'running')
        RETURNING id
        """,
        args.start, args.end, args.step_seconds, args.agents,
    )
    await conn.close()

    print(f"Backtest run ID: {run_id}")
    print(f"Period: {args.start.date()} → {args.end.date()}")
    print(f"Step: {args.step}  Agents: {', '.join(args.agents)}")

    clock = BacktestClock(start=args.start, end=args.end, step_seconds=args.step_seconds)
    print(f"Ticks: {len(clock)}")

    db = BacktestDB(dsn=settings.db_dsn, run_id=run_id)
    bus = InMemoryBus()

    await db.connect()
    await db.create_schema()

    runner = BacktestRunner(
        run_id=run_id, clock=clock, db=db, bus=bus, agent_names=args.agents
    )

    print("Running simulation...")
    await runner.run()

    print("Generating report...")
    gen = ReportGenerator(db=db, run_id=run_id)
    metrics = await gen.generate(args.output)

    if not args.keep_schema:
        await db.drop_schema()
    await db.disconnect()

    # Mark run as done
    conn = await asyncpg.connect(settings.db_dsn)
    await conn.execute(
        "UPDATE backtest_runs SET status = 'done' WHERE id = $1", run_id
    )
    await conn.close()

    print("\n=== Results ===")
    print(f"  Total Return:  {metrics['total_return_pct']:.2f}%")
    print(f"  CAGR:          {metrics['cagr_pct']:.2f}%")
    print(f"  Sharpe Ratio:  {metrics['sharpe_ratio']:.3f}")
    print(f"  Max Drawdown:  {metrics['max_drawdown_pct']:.2f}%")
    print(f"  Total Trades:  {metrics['total_trades']}")
    print(f"  Final Value:   ${metrics['final_value']:,.2f}")
    print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/backtest/test_cli.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Run full test suite**

```
pytest tests/ -v --tb=short
```
Expected: All tests pass.

- [ ] **Step 6: Commit**

```
git add backtest/cli.py tests/backtest/test_cli.py
git commit -m "feat(backtest): add CLI entry point"
```

---

## Self-Review

**Spec coverage check:**

| Spec Requirement | Covered By |
|---|---|
| `now_or_backtest()` PostgreSQL function | Task 1 |
| `backtest_runs` table | Task 1 |
| `_now()` override on BaseAgent | Task 2 |
| Python timestamp replacement in portfolio_mgr, execution, risk | Task 2 |
| `NOW()` → `now_or_backtest()` in 13 agent SQL files | Task 3 |
| `BacktestClock` tick iterator | Task 4 |
| `InMemoryBus` drop-in Redis replacement | Task 5 |
| `BacktestDB` single-connection + schema isolation + set_tick | Task 6 |
| Shadow tables (signals, trades, positions, portfolio_state) | Task 6 |
| `BacktestRunner` tiered execution, portfolio seed | Task 7 |
| Agent tier ordering (1-7) | Task 7 |
| `compute_metrics` (Sharpe, CAGR, drawdown, return) | Task 8 |
| `ReportGenerator` HTML with plotly equity + drawdown | Task 9 |
| Trade log table in report | Task 9 |
| `plotly` + `jinja2` dependencies | Task 9 |
| CLI (`--start --end --step --agents --output`) | Task 10 |
| `backtest_runs.status = 'done'` on completion | Task 10 |

**Placeholder scan:** No TBD or TODO found. All steps contain complete code.

**Type consistency:** `BacktestDB.current_tick` is `datetime | None`. `BacktestRunner._seed_portfolio` passes it correctly. `InMemoryBus.subscribe` signature matches spec. `compute_metrics` signature matches all callers.
