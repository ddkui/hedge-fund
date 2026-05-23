import pytest
from backtest.bus import InMemoryBus


async def test_set_and_get_roundtrip():
    bus = InMemoryBus()
    await bus.set("key1", {"value": 42})
    result = await bus.get("key1")
    assert result == {"value": 42}


async def test_get_missing_key_returns_none():
    bus = InMemoryBus()
    result = await bus.get("nonexistent")
    assert result is None


async def test_set_overwrites():
    bus = InMemoryBus()
    await bus.set("k", "first")
    await bus.set("k", "second")
    assert await bus.get("k") == "second"


async def test_ttl_ignored_gracefully():
    """ex= parameter is accepted without error (TTL not enforced in memory)."""
    bus = InMemoryBus()
    await bus.set("k", "v", ex=300)
    assert await bus.get("k") == "v"


async def test_subscribe_yields_nothing():
    bus = InMemoryBus()
    items = []
    async for item in bus.subscribe("channel"):
        items.append(item)
    assert items == []


async def test_publish_is_noop():
    bus = InMemoryBus()
    await bus.publish("chan", {"msg": "hello"})  # must not raise


async def test_connect_disconnect_are_noops():
    bus = InMemoryBus()
    await bus.connect()
    await bus.disconnect()  # must not raise


async def test_bus_state_persists_across_ticks():
    """Directive set at tick 1 is still readable at tick 2."""
    bus = InMemoryBus()
    await bus.set("cio:directive:AAPL", {"action": "avoid_open"})
    # Simulate tick boundary — no clear is called
    result = await bus.get("cio:directive:AAPL")
    assert result == {"action": "avoid_open"}
