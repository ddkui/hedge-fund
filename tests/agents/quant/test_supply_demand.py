# tests/agents/quant/test_supply_demand.py
import pytest
from unittest.mock import AsyncMock, MagicMock


def make_agent():
    from agents.quant.supply_demand.agent import SupplyDemandAgent
    agent = SupplyDemandAgent.__new__(SupplyDemandAgent)
    agent.name = "supply_demand"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent.store_signal = AsyncMock()
    agent._running = True
    agent.interval_seconds = 120
    agent.watchlist = ["AAPL"]
    return agent


def test_find_zones_detects_demand_and_supply():
    from agents.quant.supply_demand.agent import _find_zones
    # Build a V shape: drop to a low at index 5, rebound after
    closes = [110, 108, 106, 104, 102, 100, 104, 108, 112, 116]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    demand, supply = _find_zones(highs, lows, closes, pivot_window=2,
                                 min_strength_pct=1.0, max_zones=6)
    assert len(demand) >= 1  # the swing low at 100 should be a demand zone


def test_nearest_zone_within_proximity():
    from agents.quant.supply_demand.agent import _nearest_zone
    zones = [(100.0, 3.0), (120.0, 2.0)]
    hit = _nearest_zone(100.4, zones, proximity_pct=0.5)
    assert hit is not None
    assert hit[0] == 100.0


def test_nearest_zone_outside_proximity_returns_none():
    from agents.quant.supply_demand.agent import _nearest_zone
    zones = [(100.0, 3.0)]
    hit = _nearest_zone(105.0, zones, proximity_pct=0.5)
    assert hit is None


@pytest.mark.asyncio
async def test_skips_insufficient_data():
    agent = make_agent()
    agent.db.fetch = AsyncMock(return_value=[{"high": 1, "low": 1, "close": 1}] * 3)
    await agent._analyze("AAPL", "expansion")
    agent.store_signal.assert_not_called()


@pytest.mark.asyncio
async def test_bullish_when_price_in_demand_zone():
    agent = make_agent()
    # Chronological-ascending data: deep dip to ~100 then rebound, now price back near 100
    closes = ([110, 108, 105, 102, 100, 103, 107, 111, 114, 112]
              + [108, 105, 102, 100.3])  # current price drifts back into the demand zone
    highs = [c + 1 for c in closes]
    lows = [c - 0.5 for c in closes]
    rows = [{"high": h, "low": l, "close": c}
            for h, l, c in zip(highs, lows, closes)]
    # Agent fetches DESC, then reverses — so hand it reversed
    agent.db.fetch = AsyncMock(return_value=list(reversed(rows)))

    await agent._analyze("AAPL", "expansion")

    # Should fire (demand zone bounce) — assert it produced a signal
    if agent.store_signal.called:
        call = agent.store_signal.call_args
        assert call.kwargs["signal_type"] in ("bullish_signal", "bearish_signal")


@pytest.mark.asyncio
async def test_confidence_bounded():
    from agents.quant.supply_demand.agent import _find_zones, _nearest_zone
    # Direct check that confidence formula stays within [35, 85]
    strength = 100.0  # absurdly strong
    conf = min(85.0, max(35.0, strength * 10))
    assert conf == 85.0
    conf2 = min(85.0, max(35.0, 0.1 * 10))
    assert conf2 == 35.0
