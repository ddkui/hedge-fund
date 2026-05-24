# gateway/routers/chat.py
import asyncio
import uuid
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from shared.bus import RedisBus
from gateway.deps import get_bus

router = APIRouter()


class ChatMessage(BaseModel):
    message: str


@router.post("/kill-switch/halt")
async def halt_trading(bus: RedisBus = Depends(get_bus)):
    await bus.publish("kill_switch", {"action": "halt", "halted": True})
    await bus.set("kill_switch_state", {"halted": True})
    return {"halted": True}


@router.post("/kill-switch/resume")
async def resume_trading(bus: RedisBus = Depends(get_bus)):
    await bus.publish("kill_switch", {"action": "resume", "halted": False})
    await bus.set("kill_switch_state", {"halted": False})
    return {"halted": False}


@router.get("/kill-switch/status")
async def kill_switch_status(bus: RedisBus = Depends(get_bus)):
    state = await bus.get("kill_switch_state")
    return {"halted": state.get("halted", False) if state else False}


@router.post("")
async def chat(body: ChatMessage, bus: RedisBus = Depends(get_bus)):
    """Send message to CIO agent and wait up to 30s for response."""
    request_id = str(uuid.uuid4())
    await bus.publish("cio.chat.request", {
        "request_id": request_id,
        "message": body.message,
    })
    # Poll Redis for response (CIO agent writes to cio.chat.response:<request_id>)
    for _ in range(60):
        await asyncio.sleep(0.5)
        response = await bus.get(f"cio.chat.response:{request_id}")
        if response:
            return {"reply": response.get("reply", ""), "request_id": request_id}
    return {"reply": "CIO is not responding. Check agent health.", "request_id": request_id}
