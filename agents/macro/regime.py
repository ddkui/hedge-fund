from dataclasses import dataclass
from enum import Enum


class MacroRegime(str, Enum):
    EXPANSION = "expansion"
    CONTRACTION = "contraction"
    STAGFLATION = "stagflation"
    RECOVERY = "recovery"


class FedCycle(str, Enum):
    HIKING = "hiking"
    PAUSING = "pausing"
    CUTTING = "cutting"
    EASING = "easing"


@dataclass
class RegimeResult:
    regime: MacroRegime
    fed_cycle: FedCycle
    yield_curve_inverted: bool
    risk_on: bool
    confidence: float
    summary: str


def classify_regime(data: dict) -> RegimeResult:
    fedfunds = data.get("FEDFUNDS", 0.0)
    cpi = data.get("CPIAUCSL", 2.0)
    unrate = data.get("UNRATE", 4.0)
    dgs10 = data.get("DGS10", fedfunds + 1.5)
    gdp = data.get("GDP", 2.0)
    prev_fedfunds = data.get("FEDFUNDS_PREV", fedfunds)

    # Fed cycle
    diff = fedfunds - prev_fedfunds
    if diff >= 0.25:
        fed_cycle = FedCycle.HIKING
    elif diff <= -0.25:
        fed_cycle = FedCycle.CUTTING if fedfunds > 1.0 else FedCycle.EASING
    else:
        fed_cycle = FedCycle.PAUSING

    # Regime classification
    high_inflation = cpi > 4.0
    high_unemployment = unrate > 5.5
    negative_growth = gdp < 0.0
    sluggish_growth = gdp < 1.0
    strong_growth = gdp > 2.0

    if high_inflation and (negative_growth or high_unemployment or sluggish_growth):
        regime = MacroRegime.STAGFLATION
        confidence = 80.0
    elif negative_growth or high_unemployment:
        regime = MacroRegime.CONTRACTION
        confidence = 75.0
    elif strong_growth and not high_inflation and unrate < 4.5:
        regime = MacroRegime.EXPANSION
        confidence = 85.0
    else:
        regime = MacroRegime.RECOVERY
        confidence = 65.0

    yield_curve_inverted = dgs10 < fedfunds
    risk_on = regime in (MacroRegime.EXPANSION, MacroRegime.RECOVERY) and not yield_curve_inverted

    summary = (
        f"{regime.value.title()} regime | Fed: {fed_cycle.value} | "
        f"CPI={cpi:.1f}% UNRATE={unrate:.1f}% GDP={gdp:.1f}% | "
        f"Curve={'inverted' if yield_curve_inverted else 'normal'} | "
        f"Risk={'on' if risk_on else 'off'}"
    )

    return RegimeResult(
        regime=regime,
        fed_cycle=fed_cycle,
        yield_curve_inverted=yield_curve_inverted,
        risk_on=risk_on,
        confidence=confidence,
        summary=summary,
    )
