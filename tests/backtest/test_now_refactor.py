import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

def _make_agent():
    """Build a minimal AnalysisAgent for testing _now()."""
    import sys; sys.path.insert(0, ".")
    from agents.base import AnalysisAgent

    class DummyAgent(AnalysisAgent):
        async def run_once(self): pass

    mock_db = AsyncMock()
    mock_bus = AsyncMock()
    mock_router = MagicMock()
    return DummyAgent("test_agent", mock_bus, mock_db, mock_router)


async def test_default_now_returns_utc():
    agent = _make_agent()
    result = agent._now()
    assert result.tzinfo is not None
    # Within 2 seconds of now
    diff = abs((datetime.now(timezone.utc) - result).total_seconds())
    assert diff < 2.0


async def test_now_can_be_overridden():
    agent = _make_agent()
    fixed = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    agent._now = lambda: fixed
    assert agent._now() == fixed


async def test_store_signal_uses_now():
    agent = _make_agent()
    fixed = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    agent._now = lambda: fixed

    agent.db.execute = AsyncMock()
    agent.bus.publish = AsyncMock()

    await agent.store_signal("bullish", 0.8, "test reason", symbol="AAPL")

    call_args = agent.db.execute.call_args
    assert call_args[0][1] == fixed  # first positional arg after SQL is 'now'
