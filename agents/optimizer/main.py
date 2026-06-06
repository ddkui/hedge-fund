# agents/optimizer/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.optimizer.agent import AgentOptimizer
from agents.optimizer.alpha_monitor import AlphaMonitor


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
    optimizer = AgentOptimizer(name="optimizer", bus=bus, db=db, router=router,
                               interval_seconds=86400)
    monitor = AlphaMonitor(name="alpha_monitor", bus=bus, db=db, router=router,
                           interval_seconds=86400)
    try:
        await asyncio.gather(optimizer.run(), monitor.run())
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
