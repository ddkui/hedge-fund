# agents/optimizer/agent.py
"""
AgentOptimizer — runs every 24h.
Reads signal_outcomes, computes per-agent accuracy per regime, auto-applies
small param changes (<=10%) to agent_params.yaml, creates DB proposals for
large changes (>10%). Respects alpha_tier: skips entirely in exceptional_alpha,
micro-adjustments only in alpha_achieved.
"""
import yaml
from shared.agent_base import BaseAgent

TUNABLE_PARAMS = {
    "vwap": {
        "expansion":   {"deviation_threshold_pct": (0.5, 4.0)},
        "contraction": {"deviation_threshold_pct": (1.0, 5.0)},
        "crisis":      {"deviation_threshold_pct": (2.0, 6.0)},
        "pandemic":    {"deviation_threshold_pct": (3.0, 8.0)},
    },
    "news_momentum": {
        "expansion":   {"composite_threshold": (0.5, 3.0), "sentiment_weight": (0.2, 0.8)},
        "contraction": {"composite_threshold": (1.0, 4.0), "sentiment_weight": (0.3, 0.9)},
        "crisis":      {"composite_threshold": (2.0, 5.0), "sentiment_weight": (0.5, 0.95)},
        "pandemic":    {"composite_threshold": (3.0, 6.0), "sentiment_weight": (0.6, 0.95)},
    },
    "supply_demand": {
        "expansion":   {"min_zone_strength_pct": (0.5, 4.0), "zone_proximity_pct": (0.2, 1.0)},
        "contraction": {"min_zone_strength_pct": (1.0, 5.0), "zone_proximity_pct": (0.2, 1.0)},
        "crisis":      {"min_zone_strength_pct": (2.0, 7.0), "zone_proximity_pct": (0.2, 0.8)},
        "pandemic":    {"min_zone_strength_pct": (3.0, 9.0), "zone_proximity_pct": (0.2, 0.6)},
    },
}

MIN_SAMPLES = 10
POOR_ACCURACY_THRESHOLD = 0.45
AUTO_APPLY_MAX_CHANGE_PCT = 0.10


class AgentOptimizer(BaseAgent):
    def __init__(self, *args, params_path: str = "agent_params.yaml", **kwargs):
        super().__init__(*args, **kwargs)
        self.params_path = params_path

    async def run_once(self):
        alpha_tier = await self._get_alpha_tier()
        if alpha_tier == "exceptional_alpha":
            self.logger.info("optimizer_skipping_exceptional_alpha")
            return

        learning_rate = 0.10 if alpha_tier == "alpha_achieved" else 1.0
        active_regimes = await self._get_active_regimes()

        for agent_name, regime_params in TUNABLE_PARAMS.items():
            for regime in active_regimes:
                if regime in regime_params:
                    await self._optimize_agent(agent_name, regime, learning_rate)

    async def _get_alpha_tier(self) -> str:
        data = await self.bus.get("alpha:status") or {}
        return data.get("tier", "learning")

    async def _get_active_regimes(self) -> list[str]:
        rows = await self.db.fetch(
            "SELECT DISTINCT regime FROM signal_outcomes WHERE time > now() - INTERVAL '30 days'"
        )
        return [r["regime"] for r in rows] or ["expansion"]

    async def _compute_accuracy(self, agent_name: str, regime: str) -> tuple[float, float]:
        rows = await self.db.fetch(
            """
            SELECT was_correct, pnl FROM signal_outcomes
            WHERE agent = $1 AND regime = $2
              AND time > now() - INTERVAL '30 days' AND was_correct IS NOT NULL
            """,
            agent_name, regime,
        )
        if len(rows) < MIN_SAMPLES:
            return 0.5, 0.0
        accuracy = sum(1 for r in rows if r["was_correct"]) / len(rows)
        avg_pnl = sum(float(r["pnl"] or 0) for r in rows) / len(rows)
        return accuracy, avg_pnl

    async def _optimize_agent(self, agent_name: str, regime: str, learning_rate: float = 1.0):
        accuracy, avg_pnl = await self._compute_accuracy(agent_name, regime)
        if accuracy > POOR_ACCURACY_THRESHOLD and avg_pnl >= 0:
            return

        params = TUNABLE_PARAMS[agent_name].get(regime, {})
        current_config = self._read_param(agent_name, regime)

        for param_name, (min_val, max_val) in params.items():
            current_val = float(current_config.get(param_name, (min_val + max_val) / 2))
            adjustment = current_val * 0.05 * learning_rate
            new_val = min(max_val, max(min_val, current_val + adjustment))
            if new_val == current_val:
                continue

            change_pct = abs(new_val - current_val) / current_val if current_val != 0 else 1.0
            reason = f"accuracy={accuracy:.1%}, avg_pnl=${avg_pnl:.2f} over last 30d in {regime} regime"

            if change_pct <= AUTO_APPLY_MAX_CHANGE_PCT:
                await self._apply_change(agent_name, regime, param_name, current_val, new_val, reason)
            else:
                await self._propose_change(agent_name, regime, param_name, current_val, new_val, reason)

    def _read_param(self, agent_name: str, regime: str) -> dict:
        try:
            with open(self.params_path) as f:
                data = yaml.safe_load(f) or {}
            return data.get(agent_name, {}).get(regime, {})
        except FileNotFoundError:
            return {}

    async def _apply_change(self, agent_name: str, regime: str, param_name: str,
                            current_val: float, new_val: float, reason: str):
        try:
            with open(self.params_path) as f:
                data = yaml.safe_load(f) or {}
            data.setdefault(agent_name, {}).setdefault(regime, {})[param_name] = round(new_val, 6)
            with open(self.params_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception as exc:
            self.logger.error("optimizer_yaml_write_failed", error=str(exc))
            return

        await self.db.execute(
            "INSERT INTO optimizer_history (agent, regime, param_name, old_value, new_value, reason, auto_applied) "
            "VALUES ($1, $2, $3, $4, $5, $6, TRUE)",
            agent_name, regime, param_name, current_val, new_val, reason,
        )
        self.logger.info("optimizer_auto_applied", agent=agent_name, regime=regime,
                         param=param_name, old=current_val, new=new_val)

    async def _propose_change(self, agent_name: str, regime: str, param_name: str,
                              current_val: float, new_val: float, reason: str):
        change_pct = abs(new_val - current_val) / current_val * 100 if current_val != 0 else 100.0
        await self.db.execute(
            "INSERT INTO optimizer_proposals "
            "(agent, regime, param_name, current_value, proposed_value, change_pct, reason, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')",
            agent_name, regime, param_name, current_val, new_val, round(change_pct, 2), reason,
        )
        await self.bus.publish("optimizer.proposal", {
            "agent": agent_name, "regime": regime, "param": param_name,
            "current": current_val, "proposed": new_val, "reason": reason,
        })
        self.logger.info("optimizer_proposal_created", agent=agent_name, param=param_name,
                         change_pct=round(change_pct, 2))
