import pytest
from unittest.mock import AsyncMock
from agents.aggregator.agent import SignalAggregatorAgent, REGIME_WEIGHTS

SIGNALS_ROWS = [
    {"agent": "technical", "symbol": "AAPL", "signal_type": "macd_bullish_cross", "confidence": 75.0, "time": None},
    {"agent": "sentiment", "symbol": "AAPL", "signal_type": "sentiment_bullish", "confidence": 82.0, "time": None},
    {"agent": "macro",     "symbol": None,   "signal_type": "macro_regime_expansion", "confidence": 85.0, "time": None},
    {"agent": "research",  "symbol": "AAPL", "signal_type": "fundamental_bullish", "confidence": 78.0, "time": None},
]


def make_agent():
    return SignalAggregatorAgent(
        name="aggregator",
        bus=AsyncMock(),
        db=AsyncMock(),
        router=AsyncMock(),
        interval_seconds=120,
    )


@pytest.mark.asyncio
async def test_aggregator_stores_consensus_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    assert agent.db.execute.call_count >= 1
    call = agent.db.execute.call_args
    assert "INSERT INTO signals" in call[0][0]


@pytest.mark.asyncio
async def test_aggregator_publishes_consensus():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    channels = [c[0][0] for c in agent.bus.publish.call_args_list]
    assert any("signals.aggregator" in c for c in channels)


@pytest.mark.asyncio
async def test_aggregator_consensus_is_bullish_for_all_bullish_inputs():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=SIGNALS_ROWS)
    await agent.run_once()
    call = agent.db.execute.call_args
    signal_type = call[0][4]
    assert "bull" in signal_type or "consensus" in signal_type


@pytest.mark.asyncio
async def test_aggregator_handles_no_signals():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[])
    await agent.run_once()
    agent.db.execute.assert_not_called()


def test_regime_weights_sum_to_one():
    from agents.macro.regime import MacroRegime
    for regime in MacroRegime:
        weights = REGIME_WEIGHTS.get(regime, {})
        if weights:
            total = sum(weights.values())
            assert abs(total - 1.0) < 0.001, f"{regime}: weights sum to {total}"
