import asyncio
import pytest
from unittest.mock import AsyncMock
from shared.agent_base import BaseAgent

class ConcreteAgent(BaseAgent):
    async def run_once(self):
        return {"status": "ok"}

@pytest.mark.asyncio
async def test_agent_publishes_heartbeat():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()

    agent = ConcreteAgent(
        name="test_agent",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        interval_seconds=60,
    )
    await agent._publish_heartbeat("healthy")
    mock_bus.publish.assert_called_once_with(
        "ops.heartbeat",
        {"agent": "test_agent", "status": "healthy", "message": ""}
    )

@pytest.mark.asyncio
async def test_agent_run_calls_run_once_and_stops():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()

    agent = ConcreteAgent(
        name="test_agent",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        interval_seconds=0,  # no sleep between iterations
    )

    call_count = 0
    original_run_once = agent.run_once

    async def counting_run():
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            agent._running = False
        return await original_run_once()

    agent.run_once = counting_run
    await agent.run()
    assert call_count == 2

@pytest.mark.asyncio
async def test_agent_run_publishes_degraded_on_exception():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()

    agent = ConcreteAgent(
        name="test_agent",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
        interval_seconds=0,
    )

    async def failing_run():
        agent._running = False
        raise RuntimeError("boom")

    agent.run_once = failing_run
    await agent.run()

    calls = [str(c) for c in mock_bus.publish.call_args_list]
    assert any("degraded" in c for c in calls)

@pytest.mark.asyncio
async def test_agent_stop_sets_running_false():
    mock_bus = AsyncMock()
    mock_db = AsyncMock()
    mock_router = AsyncMock()

    agent = ConcreteAgent(
        name="test_agent",
        bus=mock_bus,
        db=mock_db,
        router=mock_router,
    )
    assert agent._running is True
    agent.stop()
    assert agent._running is False
