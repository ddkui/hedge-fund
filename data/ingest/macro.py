import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

FRED_SERIES = ["FEDFUNDS", "CPIAUCSL", "GDP", "UNRATE", "DGS10"]
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


class MacroIngestAgent(DataIngestAgent):
    def __init__(self, *args, api_key: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.api_key = api_key

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            for series_id in FRED_SERIES:
                resp = await client.get(
                    FRED_URL,
                    params={
                        "series_id": series_id,
                        "api_key": self.api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 5,
                    },
                )
                resp.raise_for_status()
                observations = resp.json().get("observations", [])
                rows = [
                    (
                        datetime.strptime(obs["date"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                        series_id,
                        float(obs["value"]),
                        "FRED",
                    )
                    for obs in observations
                    if obs["value"] != "."
                ]
                if rows:
                    await self.db.executemany(
                        "INSERT INTO macro_data (time, series_id, value, source) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                        rows,
                    )
        await self.bus.publish("data.macro.updated", {"series": FRED_SERIES})
        self.logger.info("macro_ingested", series=len(FRED_SERIES))
