import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from shared.bus import RedisBus, RedisPersistentBus

@pytest.mark.asyncio
async def test_publish_sends_json_to_channel():
    mock_redis = AsyncMock()
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        await bus.publish("signals.quant", {"symbol": "AAPL", "direction": "bull"})
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args
        assert call_args[0][0] == "signals.quant"
        assert '"symbol": "AAPL"' in call_args[0][1]

@pytest.mark.asyncio
async def test_subscribe_yields_parsed_messages():
    mock_redis = AsyncMock()
    mock_pubsub = AsyncMock()
    mock_redis.pubsub = MagicMock(return_value=mock_pubsub)
    mock_pubsub.subscribe = AsyncMock()

    async def fake_listen():
        yield {"type": "message", "data": b'{"symbol": "BTC", "direction": "bear"}'}
        yield {"type": "subscribe", "data": 1}

    mock_pubsub.listen = fake_listen

    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        messages = []
        async for msg in bus.subscribe("signals.quant"):
            messages.append(msg)
            break
        assert messages[0]["symbol"] == "BTC"

@pytest.mark.asyncio
async def test_disconnect_closes_client():
    mock_redis = AsyncMock()
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        await bus.disconnect()
        mock_redis.aclose.assert_called_once()

@pytest.mark.asyncio
async def test_set_stores_json_value():
    mock_redis = AsyncMock()
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        await bus.set("portfolio.value", {"total": 10000}, ex=60)
        mock_redis.set.assert_called_once_with("portfolio.value", '{"total": 10000}', ex=60)

@pytest.mark.asyncio
async def test_get_returns_parsed_value():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value='{"total": 10000}')
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        result = await bus.get("portfolio.value")
        assert result == {"total": 10000}

@pytest.mark.asyncio
async def test_get_returns_none_for_missing_key():
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisBus("redis://localhost:6379/0")
        await bus.connect()
        result = await bus.get("nonexistent")
        assert result is None


# --- RedisPersistentBus tests ---

@pytest.mark.asyncio
async def test_persistent_bus_publish_uses_xadd():
    mock_redis = AsyncMock()
    mock_redis.xadd = AsyncMock(return_value="1234567890-0")
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisPersistentBus("redis://localhost:6379/0")
        await bus.connect()
        msg_id = await bus.publish("signals.stream", {"symbol": "AAPL", "direction": "bull"})
        mock_redis.xadd.assert_called_once()
        args = mock_redis.xadd.call_args[0]
        assert args[0] == "signals.stream"
        assert msg_id == "1234567890-0"


@pytest.mark.asyncio
async def test_persistent_bus_subscribe_yields_messages():
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock()
    mock_redis.xack = AsyncMock()

    first = True

    async def fake_xreadgroup(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            return [("signals.stream", [("0-1", {"data": '{"symbol": "BTC"}'})])]
        await asyncio.sleep(999)
        return []

    mock_redis.xreadgroup = fake_xreadgroup

    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisPersistentBus("redis://localhost:6379/0", group="g1", consumer="c1")
        await bus.connect()
        messages = []

        async def collect():
            async for msg in bus.subscribe("signals.stream"):
                messages.append(msg)
                break

        task = asyncio.create_task(collect())
        await asyncio.wait_for(task, timeout=2.0)

    assert len(messages) == 1
    assert messages[0]["symbol"] == "BTC"


@pytest.mark.asyncio
async def test_persistent_bus_handles_existing_consumer_group():
    mock_redis = AsyncMock()
    mock_redis.xgroup_create = AsyncMock(
        side_effect=Exception("BUSYGROUP Consumer Group name already exists")
    )
    mock_redis.xack = AsyncMock()

    first = True

    async def fake_xreadgroup(*args, **kwargs):
        nonlocal first
        if first:
            first = False
            return [("signals.stream", [("0-1", {"data": '{"event": "tick"}'})])]
        await asyncio.sleep(999)
        return []

    mock_redis.xreadgroup = fake_xreadgroup

    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisPersistentBus("redis://localhost:6379/0")
        await bus.connect()
        messages = []

        async def collect():
            async for msg in bus.subscribe("signals.stream"):
                messages.append(msg)
                break

        task = asyncio.create_task(collect())
        await asyncio.wait_for(task, timeout=2.0)

    assert len(messages) == 1
    assert messages[0]["event"] == "tick"


@pytest.mark.asyncio
async def test_persistent_bus_disconnect():
    mock_redis = AsyncMock()
    with patch("shared.bus.redis.asyncio.from_url", return_value=mock_redis):
        bus = RedisPersistentBus("redis://localhost:6379/0")
        await bus.connect()
        await bus.disconnect()
        mock_redis.aclose.assert_called_once()
