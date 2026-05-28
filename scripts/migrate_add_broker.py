#!/usr/bin/env python3
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
