#!/usr/bin/env python3
"""
Starts all data ingest agents concurrently in a single process.
Each agent runs its own async loop on its own interval.
"""
import asyncio
import sys
sys.path.insert(0, ".")

from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from data.ingest.stocks import StocksIngestAgent
from data.ingest.crypto import CryptoIngestAgent
from data.ingest.macro import MacroIngestAgent
from data.ingest.news import NewsIngestAgent
from data.ingest.sec import SecIngestAgent
from data.ingest.social import SocialIngestAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(settings)

    await bus.connect()
    await db.connect()

    watchlist = settings.stock_watchlist.split(",")
    crypto_watchlist = settings.crypto_watchlist.split(",")

    agents = [
        StocksIngestAgent(name="stocks_ingest", bus=bus, db=db, router=router, watchlist=watchlist, interval_seconds=60),
        CryptoIngestAgent(name="crypto_ingest", bus=bus, db=db, router=router, watchlist=crypto_watchlist, interval_seconds=30),
        MacroIngestAgent(name="macro_ingest", bus=bus, db=db, router=router, api_key=settings.fred_api_key, interval_seconds=3600),
        NewsIngestAgent(name="news_ingest", bus=bus, db=db, router=router, api_key=settings.news_api_key, interval_seconds=300),
        SecIngestAgent(name="sec_ingest", bus=bus, db=db, router=router, watchlist=watchlist, interval_seconds=3600),
        SocialIngestAgent(
            name="social_ingest", bus=bus, db=db, router=router,
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            user_agent=settings.reddit_user_agent,
            interval_seconds=300,
        ),
    ]

    try:
        await asyncio.gather(*[agent.run() for agent in agents])
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
