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
