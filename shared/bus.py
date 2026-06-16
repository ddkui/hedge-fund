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


class RedisPersistentBus:
    """At-least-once message bus using Redis Streams (XADD / XREADGROUP / XACK).

    Messages survive subscriber downtime via consumer groups. Each message is
    acknowledged after it is yielded to the caller, preserving at-least-once
    delivery semantics.
    """

    def __init__(self, url: str, group: str = "hedge-fund", consumer: str = "worker-1"):
        self._url = url
        self._group = group
        self._consumer = consumer
        self._client: redis.asyncio.Redis | None = None

    async def connect(self):
        self._client = redis.asyncio.from_url(self._url, decode_responses=True)

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    async def publish(self, stream: str, message: dict[str, Any]) -> str:
        """XADD message to stream; returns the assigned message id."""
        return await self._client.xadd(stream, {"data": json.dumps(message)})

    async def subscribe(self, stream: str) -> "AsyncIterator[dict[str, Any]]":
        """XREADGROUP loop — yields messages, XACK after delivery."""
        try:
            await self._client.xgroup_create(stream, self._group, id="0", mkstream=True)
        except Exception:
            pass  # BUSYGROUP: group already exists — continue normally

        while True:
            results = await self._client.xreadgroup(
                self._group,
                self._consumer,
                {stream: ">"},
                count=10,
                block=1000,
            )
            if not results:
                continue
            for stream_name, messages in results:
                for msg_id, fields in messages:
                    data = json.loads(fields.get("data", "{}"))
                    yield data
                    await self._client.xack(stream_name, self._group, msg_id)
