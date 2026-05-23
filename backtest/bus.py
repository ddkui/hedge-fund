from typing import Any, AsyncIterator


class InMemoryBus:
    def __init__(self):
        self._store: dict[str, Any] = {}

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    async def set(self, key: str, value: Any, ex: int | None = None):
        self._store[key] = value

    async def get(self, key: str) -> Any | None:
        return self._store.get(key)

    async def publish(self, channel: str, message: Any):
        pass

    async def subscribe(self, channel: str) -> AsyncIterator[Any]:
        return
        yield
