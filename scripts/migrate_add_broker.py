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
    if not settings.db_dsn:
        print("ERROR: DB_DSN not configured")
        sys.exit(1)

    print("Connecting to TimescaleDB...")
    conn = None
    try:
        conn = await asyncpg.connect(settings.db_dsn)
        print("Running migration...")
        await conn.execute(MIGRATION)
        print("Migration complete: trades.broker and trades.asset_class added.")
    except Exception as exc:
        print(f"ERROR: Migration failed: {exc}")
        sys.exit(1)
    finally:
        if conn:
            await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
