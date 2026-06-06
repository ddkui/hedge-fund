# agents/quant/supply_demand/agent.py
"""
Supply & Demand quant agent.

Identifies demand zones (swing lows = support) and supply zones (swing highs =
resistance) from recent price history using fractal pivots. When the current
price drops into a demand zone it emits bullish (expect a bounce); when it
rises into a supply zone it emits bearish (expect rejection). Zone strength —
the size of the original reversal move — scales confidence.

Regime-aware: thresholds are loaded per macro regime from agent_params.yaml.
"""
from agents.base import AnalysisAgent
from shared.agent_params import load_agent_params

DEFAULTS = {
    "lookback": 120,           # candles of history to scan for zones
    "pivot_window": 3,         # candles each side to qualify a swing pivot
    "zone_proximity_pct": 0.5, # how close (%) price must be to a zone to trigger
    "min_zone_strength_pct": 1.5,  # min reversal size (%) for a zone to count
    "max_zones": 6,            # keep the N strongest zones per side
}


def _find_zones(highs: list[float], lows: list[float], closes: list[float],
                pivot_window: int, min_strength_pct: float, max_zones: int):
    """Return (demand_zones, supply_zones) as lists of (price, strength_pct)."""
    demand: list[tuple[float, float]] = []
    supply: list[tuple[float, float]] = []
    n = len(closes)

    for i in range(pivot_window, n - pivot_window):
        window_lows = lows[i - pivot_window:i + pivot_window + 1]
        window_highs = highs[i - pivot_window:i + pivot_window + 1]

        # Demand: local minimum (swing low)
        if lows[i] == min(window_lows):
            # Strength = rebound from this low to the highest close after it
            forward = closes[i:i + pivot_window + 1]
            rebound = (max(forward) - lows[i]) / lows[i] * 100 if lows[i] > 0 else 0.0
            if rebound >= min_strength_pct:
                demand.append((lows[i], rebound))

        # Supply: local maximum (swing high)
        if highs[i] == max(window_highs):
            forward = closes[i:i + pivot_window + 1]
            drop = (highs[i] - min(forward)) / highs[i] * 100 if highs[i] > 0 else 0.0
            if drop >= min_strength_pct:
                supply.append((highs[i], drop))

    demand.sort(key=lambda z: z[1], reverse=True)
    supply.sort(key=lambda z: z[1], reverse=True)
    return demand[:max_zones], supply[:max_zones]


def _nearest_zone(price: float, zones: list[tuple[float, float]], proximity_pct: float):
    """Return (zone_price, strength) of the closest zone within proximity, else None."""
    best = None
    best_dist = proximity_pct
    for zone_price, strength in zones:
        if zone_price <= 0:
            continue
        dist = abs(price - zone_price) / zone_price * 100
        if dist <= best_dist:
            best_dist = dist
            best = (zone_price, strength)
    return best


class SupplyDemandAgent(AnalysisAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist

    async def run_once(self):
        regime_data = await self.bus.get("macro:current_regime") or {}
        regime = regime_data.get("regime", "expansion")
        for symbol in self.watchlist:
            await self._analyze(symbol, regime)

    async def _analyze(self, symbol: str, regime: str):
        params = load_agent_params("supply_demand", regime, DEFAULTS)
        lookback = int(params["lookback"])
        pivot_window = int(params["pivot_window"])
        proximity = float(params["zone_proximity_pct"])
        min_strength = float(params["min_zone_strength_pct"])
        max_zones = int(params["max_zones"])

        rows = await self.db.fetch(
            "SELECT high, low, close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT $2",
            symbol, lookback,
        )
        if len(rows) < pivot_window * 2 + 5:
            return

        # rows are DESC; reverse to chronological
        rows = list(reversed(rows))
        highs = [float(r["high"]) for r in rows]
        lows = [float(r["low"]) for r in rows]
        closes = [float(r["close"]) for r in rows]
        current_price = closes[-1]

        # Build zones from everything except the most recent pivot_window candles
        demand, supply = _find_zones(
            highs[:-pivot_window], lows[:-pivot_window], closes[:-pivot_window],
            pivot_window, min_strength, max_zones,
        )

        demand_hit = _nearest_zone(current_price, demand, proximity)
        supply_hit = _nearest_zone(current_price, supply, proximity)

        # If price sits in both, the stronger zone wins
        signal_type = None
        zone_price = None
        strength = 0.0
        if demand_hit and (not supply_hit or demand_hit[1] >= supply_hit[1]):
            signal_type = "bullish_signal"
            zone_price, strength = demand_hit
            zone_kind = "demand"
        elif supply_hit:
            signal_type = "bearish_signal"
            zone_price, strength = supply_hit
            zone_kind = "supply"
        else:
            return

        confidence = min(85.0, max(35.0, strength * 10))

        await self.store_signal(
            symbol=symbol,
            signal_type=signal_type,
            confidence=round(confidence, 2),
            reasoning=(
                f"Price {current_price:.4f} entered {zone_kind} zone at {zone_price:.4f} "
                f"(reversal strength {strength:.2f}%), regime={regime}"
            ),
            metadata={
                "zone_kind": zone_kind,
                "zone_price": round(zone_price, 6),
                "current_price": round(current_price, 6),
                "strength_pct": round(strength, 4),
                "demand_zone_count": len(demand),
                "supply_zone_count": len(supply),
                "regime": regime,
            },
        )
        self.logger.info("supply_demand_signal", symbol=symbol,
                         signal=signal_type, zone=zone_kind, strength=round(strength, 2))
