import json
import uuid
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
    """
    Persistent message bus using Redis Streams (XADD/XREADGROUP/XACK).
    Guarantees at-least-once delivery — messages survive subscriber downtime.
    """

    def __init__(self, url: str, consumer_group: str = "hedge-fund", consumer_name: str | None = None):
        self._url = url
        self._group = consumer_group
        self._consumer = consumer_name or f"consumer-{uuid.uuid4().hex[:8]}"
        self._client: redis.asyncio.Redis | None = None

    async def connect(self):
        self._client = redis.asyncio.from_url(self._url, decode_responses=True)

    async def disconnect(self):
        if self._client:
            await self._client.aclose()

    async def _ensure_group(self, stream: str) -> None:
        """Create consumer group if it doesn't exist."""
        try:
            await self._client.xgroup_create(stream, self._group, id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise

    async def publish(self, channel: str, message: dict[str, Any]) -> str:
        """XADD message to stream. Returns message ID."""
        msg_id = await self._client.xadd(channel, {"data": json.dumps(message)})
        return msg_id

    async def subscribe(self, channel: str) -> AsyncIterator[dict[str, Any]]:  # type: ignore[override]
        """XREADGROUP with ACK — at-least-once delivery."""
        await self._ensure_group(channel)
        while True:
            results = await self._client.xreadgroup(
                self._group,
                self._consumer,
                {channel: ">"},
                count=10,
                block=1000,
            )
            if not results:
                continue
            for _stream, messages in results:
                for msg_id, fields in messages:
                    try:
                        data = json.loads(fields["data"])
                        await self._client.xack(channel, self._group, msg_id)
                        yield data
                    except Exception:
                        # Leave unacked for retry
                        pass

    async def set(self, key: str, value: Any, ex: int | None = None):
        await self._client.set(key, json.dumps(value), ex=ex)

    async def get(self, key: str) -> Any | None:
        val = await self._client.get(key)
        return json.loads(val) if val else None

    async def delete(self, key: str):
        await self._client.delete(key)
