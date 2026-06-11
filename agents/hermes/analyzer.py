"""
Hermes analyzer: reads signal_outcomes, computes per-agent win rates,
and proposes aggregator weight adjustments.
"""
from datetime import datetime, timezone
from typing import Any

from agents.hermes.models import WeightProposal

_LOOKBACK_DAYS = 30
_MIN_SAMPLES = 10
_STEP_UP = 1.05    # +5% for high performers
_STEP_DOWN = 0.95  # -5% for poor performers
_WEIGHT_CAP = 2.5
_WEIGHT_FLOOR = 0.1
_WIN_HIGH = 0.70
_WIN_LOW = 0.45


async def collect_win_rates(db) -> list[dict]:
    """Aggregate signal_outcomes into per-agent/regime win rates."""
    return await db.fetch(
        f"""
        SELECT agent, regime,
               COUNT(*) FILTER (WHERE was_correct = TRUE)  AS wins,
               COUNT(*) FILTER (WHERE was_correct IS NOT NULL) AS total
        FROM signal_outcomes
        WHERE time > NOW() - INTERVAL '{_LOOKBACK_DAYS} days'
          AND was_correct IS NOT NULL
        GROUP BY agent, regime
        HAVING COUNT(*) FILTER (WHERE was_correct IS NOT NULL) > 0
        """
    )


def compute_weight_proposals(
    stats: list[dict],
    yaml_data: dict[str, Any],
    auto_threshold_pct: float = 10.0,
) -> list[WeightProposal]:
    """
    For each agent/regime with enough samples, propose a ±5% aggregator
    weight change. Changes < auto_threshold_pct are flagged auto_apply.
    """
    proposals: list[WeightProposal] = []

    for row in stats:
        agent = row["agent"]
        regime = row["regime"]
        total = int(row["total"])
        wins = int(row["wins"])

        if total < _MIN_SAMPLES:
            continue

        win_rate = wins / total

        agg = yaml_data.get("aggregator", {})
        regime_weights = (agg.get(regime) or agg.get("_default") or {}).get("agent_weights", {})
        current = regime_weights.get(agent)
        if current is None:
            continue

        if win_rate >= _WIN_HIGH:
            proposed = round(min(current * _STEP_UP, _WEIGHT_CAP), 3)
        elif win_rate < _WIN_LOW:
            proposed = round(max(current * _STEP_DOWN, _WEIGHT_FLOOR), 3)
        else:
            continue

        if proposed == current:
            continue

        change_pct = abs((proposed - current) / current) * 100
        proposals.append(WeightProposal(
            agent_name=agent,
            regime=regime,
            current_weight=current,
            proposed_weight=proposed,
            win_rate=win_rate,
            total_signals=total,
            auto_apply=change_pct < auto_threshold_pct,
        ))

    return proposals


def apply_yaml_proposals(yaml_data: dict[str, Any], proposals: list[WeightProposal]) -> dict[str, Any]:
    """Apply auto_apply proposals to yaml_data in-place and update _meta timestamp."""
    for p in proposals:
        if not p.auto_apply:
            continue
        regime_section = yaml_data.get("aggregator", {}).get(p.regime)
        if regime_section and "agent_weights" in regime_section:
            regime_section["agent_weights"][p.agent_name] = p.proposed_weight
    yaml_data.setdefault("_meta", {})["last_updated"] = datetime.now(timezone.utc).isoformat()
    return yaml_data
