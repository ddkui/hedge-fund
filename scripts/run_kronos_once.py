#!/usr/bin/env python3
"""One-shot Kronos research run — loads model, forecasts all symbols, exits."""
import asyncio
import sys
sys.path.insert(0, ".")

from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings
from shared.model_router import ModelRouter
from agents.quant.kronos.agent import KronosResearchAgent


async def main():
    print("Connecting to DB and Redis...")
    db = Database(settings.db_dsn)
    bus = RedisBus(settings.redis_url)
    await db.connect()
    await bus.connect()

    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    agent = KronosResearchAgent(
        name="kronos",
        db=db,
        bus=bus,
        router=router,
        interval_seconds=0,
    )

    print("Loading Kronos model (downloads ~200 MB on first run)...")
    await asyncio.get_event_loop().run_in_executor(None, agent._load_model)

    if not agent._model_loaded:
        print(f"ERROR: model failed to load — {agent._load_error}")
        sys.exit(1)

    print("Model ready. Running forecast...")
    await agent.run_once()
    print("\nDone. Check memory/obsidian/kronos/ for the report.")

    await db.disconnect()
    await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
