import asyncpg

class Database:
    def __init__(self, dsn: str):
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def fetch(self, query: str, *args) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    async def fetchrow(self, query: str, *args) -> dict | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def execute(self, query: str, *args):
        async with self.pool.acquire() as conn:
            await conn.execute(query, *args)

    async def executemany(self, query: str, args_list: list):
        async with self.pool.acquire() as conn:
            await conn.executemany(query, args_list)
