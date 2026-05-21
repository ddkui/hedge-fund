import pytest
from unittest.mock import AsyncMock
from agents.macro.agent import MacroResearchAgent

MACRO_ROWS = [
    {"series_id": "FEDFUNDS", "value": 5.33, "time": None},
    {"series_id": "CPIAUCSL", "value": 3.2, "time": None},
    {"series_id": "UNRATE", "value": 3.8, "time": None},
    {"series_id": "DGS10", "value": 4.25, "time": None},
    {"series_id": "GDP", "value": 2.9, "time": None},
]


def make_agent():
    return MacroResearchAgent(
        name="macro",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=3600,
    )


@pytest.mark.asyncio
async def test_macro_agent_stores_regime_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=MACRO_ROWS)
    agent.router.chat = AsyncMock(return_value="Markets in late-cycle expansion. Fed likely to pause.")
    await agent.run_once()
    agent.db.execute.assert_called_once()
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]


@pytest.mark.asyncio
async def test_macro_agent_publishes_regime():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=MACRO_ROWS)
    agent.router.chat = AsyncMock(return_value="Expansion with hawkish Fed.")
    await agent.run_once()
    agent.bus.publish.assert_called()
    calls = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.macro" in c for c in calls)


@pytest.mark.asyncio
async def test_macro_agent_handles_missing_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()
