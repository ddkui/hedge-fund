# agents/quant/news_momentum/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.quant.news_momentum.agent import NewsMomentumAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    watchlist = [s.strip() for s in
                 (settings.stock_watchlist + "," + settings.crypto_watchlist).split(",")
                 if s.strip()]
    agent = NewsMomentumAgent(
        name="news_momentum", bus=bus, db=db, router=router,
        watchlist=watchlist, interval_seconds=120,
    )
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
