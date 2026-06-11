#!/usr/bin/env python3
"""Add hermes_patches table for code improvement proposals."""
import asyncio
import asyncpg
import sys
sys.path.insert(0, ".")
from shared.config import settings

SQL = """
CREATE TABLE IF NOT EXISTS hermes_patches (
    id          BIGSERIAL PRIMARY KEY,
    time        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent_name  TEXT NOT NULL,
    regime      TEXT,
    win_rate    DOUBLE PRECISION,
    file_path   TEXT NOT NULL,
    description TEXT NOT NULL,
    original_content TEXT NOT NULL,
    patched_content  TEXT NOT NULL,
    reason      TEXT,
    status      TEXT NOT NULL DEFAULT 'pending',
    applied_at  TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS hermes_patches_status ON hermes_patches(status, time DESC);
"""

async def main():
    conn = await asyncpg.connect(settings.db_dsn)
    await conn.execute(SQL)
    await conn.close()
    print("hermes_patches table created.")

if __name__ == "__main__":
    asyncio.run(main())
