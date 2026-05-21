import asyncio
from abc import ABC, abstractmethod
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from shared.logging import get_logger

class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        bus: RedisBus,
        db: Database,
        router: ModelRouter,
        interval_seconds: int = 60,
    ):
        self.name = name
        self.bus = bus
        self.db = db
        self.router = router
        self.interval_seconds = interval_seconds
        self._running = True
        self.logger = get_logger(name)

    @abstractmethod
    async def run_once(self):
        """Run one cycle of agent logic. Implement in subclass."""

    async def _publish_heartbeat(self, status: str, message: str = ""):
        await self.bus.publish("ops.heartbeat", {
            "agent": self.name,
            "status": status,
            "message": message,
        })

    async def run(self):
        self.logger.info("agent_starting", interval=self.interval_seconds)
        await self._publish_heartbeat("healthy", "starting")
        while self._running:
            try:
                await self.run_once()
                await self._publish_heartbeat("healthy")
            except Exception as e:
                self.logger.error("run_once_failed", error=str(e))
                await self._publish_heartbeat("degraded", str(e))
            if self._running:
                await asyncio.sleep(self.interval_seconds)

    def stop(self):
        self._running = False
