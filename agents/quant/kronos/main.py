import asyncio
import sys
sys.path.insert(0, ".")

from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings
from shared.model_router import ModelRouter
from agents.quant.kronos.agent import KronosResearchAgent


async def main():
    db = Database(settings.db_dsn)
    bus = RedisBus(settings.redis_url)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await db.connect()
    await bus.connect()
    agent = KronosResearchAgent(
        name="kronos",
        db=db,
        bus=bus,
        router=router,
        interval_seconds=6 * 3600,
    )
    try:
        await agent.run()
    finally:
        await db.disconnect()
        await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
