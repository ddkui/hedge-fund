# gateway/ws_manager.py
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# Redis channels to forward to all connected WebSocket clients
SUBSCRIBED_CHANNELS = [
    "ops.heartbeat",
    "signals.technical",
    "signals.sentiment",
    "signals.macro",
    "signals.research",
    "signals.aggregator",
    "signals.quant_supervisor",
    "signals.portfolio_mgr",
    "data.prices",
    "data.news",
]

_clients: list[WebSocket] = []


async def _broadcast(message: dict):
    disconnected = []
    for ws in list(_clients):
        try:
            await ws.send_text(json.dumps(message))
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        _clients.remove(ws)


async def _redis_bridge():
    """Subscribe to all channels and broadcast to WebSocket clients."""
    import redis.asyncio as aioredis
    from shared.config import settings
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(*SUBSCRIBED_CHANNELS)
        async for raw in pubsub.listen():
            if raw["type"] == "message":
                data = raw["data"]
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = {"raw": data}
                await _broadcast({"channel": raw["channel"], "data": payload})
    finally:
        await pubsub.unsubscribe()
        await client.aclose()


_bridge_task: asyncio.Task | None = None


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    global _bridge_task
    await ws.accept()
    _clients.append(ws)

    # Start bridge task once
    if _bridge_task is None or _bridge_task.done():
        _bridge_task = asyncio.create_task(_redis_bridge())

    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(30)
            await ws.send_text(json.dumps({"type": "ping"}))
    except (WebSocketDisconnect, Exception):
        if ws in _clients:
            _clients.remove(ws)
