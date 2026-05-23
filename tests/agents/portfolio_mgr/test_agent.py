import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.portfolio_mgr.agent import PortfolioManagerAgent

AGG_SIGNAL = {"agent": "aggregator", "symbol": "AAPL", "signal_type": "consensus_bullish", "confidence": 80.0, "time": None}
QUANT_SIGNAL = {"agent": "quant_supervisor", "symbol": "AAPL", "signal_type": "quant_bullish", "confidence": 70.0, "time": None}
PORTFOLIO_ROW = {"cash": 100_000.0, "total_value": 100_000.0, "peak_value": 100_000.0, "open_positions": 0}
PRICE_ROW = {"close": 150.0}


def make_agent():
    settings = MagicMock()
    settings.kelly_multiplier = 0.25
    settings.risk_max_position_pct = 0.10
    settings.risk_max_positions = 10
    settings.risk_max_drawdown_pct = 0.20
    settings.risk_var_limit_pct = 0.05
    settings.risk_max_correlated = 3
    settings.paper_trading = True
    settings.initial_capital = 100_000.0
    with patch("agents.portfolio_mgr.agent.settings", settings):
        agent = PortfolioManagerAgent(
            name="portfolio_mgr",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=120,
        )
    agent._settings = settings
    return agent


@pytest.mark.asyncio
async def test_pm_opens_long_on_bullish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],          # aggregator signals
        [QUANT_SIGNAL],        # quant_supervisor signals
        [],                    # existing positions
        [PRICE_ROW],           # current price fetch
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)  # no CIO directive

    # Mock RiskChecker to approve
    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(True, ""))
        await agent.run_once()

    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    assert "long" in args
    assert "pending" in args


@pytest.mark.asyncio
async def test_pm_skips_when_position_already_open():
    agent = make_agent()
    open_pos = {"symbol": "AAPL", "direction": "long", "quantity": 5.0, "status": "open"}
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [open_pos],     # already long AAPL
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    await agent.run_once()
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 0


@pytest.mark.asyncio
async def test_pm_applies_cio_low_conviction():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    # CIO says low_conviction with 0.5 multiplier
    agent.bus.get = AsyncMock(return_value={"action": "low_conviction", "confidence_multiplier": 0.5, "reason": "uncertain"})

    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(True, ""))
        await agent.run_once()

    # Should still open but with lower confidence
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    confidence = args[7]   # confidence is 8th positional arg to db.execute (0-indexed: time, symbol, direction, quantity, paper, reasoning, confidence)
    assert confidence < 76.0  # (0.6*80 + 0.4*70) * 0.5 = 76 * 0.5 = 38


@pytest.mark.asyncio
async def test_pm_risk_rejection_writes_risk_event():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(False, "drawdown: 25% exceeds max 20%"))
        await agent.run_once()

    risk_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO risk_events" in str(c)]
    assert len(risk_calls) == 1


@pytest.mark.asyncio
async def test_pm_closes_on_neutral_signal():
    agent = make_agent()
    neutral_signal = {**AGG_SIGNAL, "signal_type": "consensus_neutral"}
    open_pos = {"symbol": "AAPL", "direction": "long", "quantity": 5.0, "status": "open"}
    agent.db.fetch = AsyncMock(side_effect=[
        [neutral_signal],
        [],        # no quant signal
        [open_pos],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    await agent.run_once()
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    assert "close" in args
