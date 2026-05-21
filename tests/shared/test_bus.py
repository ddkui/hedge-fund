import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from shared.bus import RedisBus

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
