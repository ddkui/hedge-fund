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
