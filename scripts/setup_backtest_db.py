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
