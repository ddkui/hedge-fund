import json
import redis
import redis.asyncio
from typing import AsyncIterator, Any

class RedisBus:
    def __init__(self, url: str):
        self._url = url
        self._client: redis.asyncio.Redis | None = None

    async def connect(self):
        self._client = redis.asyncio.from_url(self._url, decode_responses=True)

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    async def publish(self, channel: str, message: dict[str, Any]):
        await self._client.publish(channel, json.dumps(message))

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:  # type: ignore[override]
        pubsub = self._client.pubsub()
        await pubsub.subscribe(channel)
        async for raw in pubsub.listen():
            if raw["type"] == "message":
                data = raw["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                yield json.loads(data)

    async def set(self, key: str, value: Any, ex: int | None = None):
        await self._client.set(key, json.dumps(value), ex=ex)

    async def get(self, key: str) -> Any | None:
        val = await self._client.get(key)
        return json.loads(val) if val else None

    async def delete(self, key: str):
        await self._client.delete(key)
