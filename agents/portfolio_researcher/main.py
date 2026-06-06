# agents/portfolio_researcher/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings
from agents.portfolio_researcher.agent import PortfolioResearcherAgent


async def main():
    db = Database(settings.db_dsn)
    bus = RedisBus(settings.redis_url)
    await db.connect()
    await bus.connect()
    agent = PortfolioResearcherAgent(
        name="portfolio_researcher",
        db=db,
        bus=bus,
        interval_seconds=1800,
    )
    try:
        await agent.run()
    finally:
        await db.disconnect()
        await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
