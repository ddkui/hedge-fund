import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.cio.agent import CIOAgent

OPEN_POSITIONS = [{"symbol": "AAPL", "direction": "long", "quantity": 10.0, "entry_price": 145.0, "status": "open"}]
PRICE_ROW = [{"symbol": "AAPL", "close": 150.0}]
CLOSED_TRADES = []
MACRO_SIGNAL = [{"signal_type": "expansion", "confidence": 70.0, "time": None}]
RISK_EVENTS = []
CIO_OVERRIDES = []

LLM_RESPONSE = json.dumps([
    {"symbol": "AAPL", "action": "low_conviction", "confidence_multiplier": 0.7, "reason": "earnings uncertainty"}
])


def make_agent():
    with patch("agents.cio.agent.settings"):
        agent = CIOAgent(
            name="cio",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=3600,
        )
    return agent


@pytest.mark.asyncio
async def test_cio_publishes_directive_to_redis():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],                # last 24h signals
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value=LLM_RESPONSE)

    with patch("agents.cio.agent.settings"):
        await agent.run_once()

    set_calls = [c for c in agent.bus.set.call_args_list]
    keys = [c[0][0] for c in set_calls]
    assert any("cio:directive:AAPL" in k for k in keys)


@pytest.mark.asyncio
async def test_cio_writes_daily_brief_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value=LLM_RESPONSE)

    with patch("agents.cio.agent.settings"):
        await agent.run_once()

    signal_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO signals" in str(c)]
    assert len(signal_calls) >= 1
    args = signal_calls[0][0]
    assert "daily_brief" in args


@pytest.mark.asyncio
async def test_cio_handles_malformed_llm_response():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value="not valid json at all")

    with patch("agents.cio.agent.settings"):
        await agent.run_once()

    # Should not crash; still writes daily brief with no directives
    signal_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO signals" in str(c)]
    assert len(signal_calls) >= 1
