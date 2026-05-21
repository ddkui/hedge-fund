from shared.agent_base import BaseAgent


class DataIngestAgent(BaseAgent):
    async def store_prices(self, rows: list[dict]):
        if not rows:
            return
        await self.db.executemany(
            """
            INSERT INTO prices (time, symbol, asset_class, open, high, low, close, volume)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT ON CONSTRAINT prices_time_symbol_unique DO NOTHING
            """,
            [
                (
                    r["time"],
                    r["symbol"],
                    r["asset_class"],
                    r.get("open"),
                    r.get("high"),
                    r.get("low"),
                    r["close"],
                    r.get("volume"),
                )
                for r in rows
            ],
        )
