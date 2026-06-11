import os
import yaml
from shared.agent_base import BaseAgent
from agents.hermes import analyzer
from agents.hermes.models import WeightProposal


class HermesAgent(BaseAgent):
    """
    Self-improvement meta-agent. Hourly cycle:
    1. Computes per-agent win rates from signal_outcomes.
    2. Proposes ±5% aggregator weight changes for over/under performers.
    3. Auto-applies small changes (<10%); queues larger ones for CIO approval.
    4. Publishes a summary to ops.hermes via the bus.
    """

    def __init__(self, *args, params_path: str = "agent_params.yaml", **kwargs):
        super().__init__(*args, **kwargs)
        self.params_path = params_path

    async def run_once(self) -> None:
        stats = await analyzer.collect_win_rates(self.db)

        yaml_data = self._load_yaml()
        proposals = analyzer.compute_weight_proposals(stats, yaml_data)

        auto_proposals = [p for p in proposals if p.auto_apply]
        pending_proposals = [p for p in proposals if not p.auto_apply]

        if auto_proposals:
            analyzer.apply_yaml_proposals(yaml_data, auto_proposals)
            self._save_yaml(yaml_data)
            for p in auto_proposals:
                await self._record_applied(p)

        for p in pending_proposals:
            await self._queue_for_approval(p)

        summary = await self._llm_summary(len(stats), auto_proposals, pending_proposals)

        total_outcomes = sum(int(r["total"]) for r in stats)
        await self.bus.publish("ops.hermes", {
            "agent": self.name,
            "cycle_time": self._now().isoformat(),
            "outcomes_analyzed": total_outcomes,
            "proposals_generated": len(proposals),
            "auto_applied": len(auto_proposals),
            "queued_for_approval": len(pending_proposals),
            "summary": summary,
        })
        self.logger.info(
            "hermes_cycle_complete",
            agent_regimes=len(stats),
            auto_applied=len(auto_proposals),
            queued=len(pending_proposals),
        )

    async def _record_applied(self, p: WeightProposal) -> None:
        await self.db.execute(
            "INSERT INTO optimizer_history "
            "(agent, regime, param_name, old_value, new_value, reason, auto_applied) "
            "VALUES ($1, $2, $3, $4, $5, $6, TRUE)",
            p.agent_name, p.regime,
            f"aggregator.agent_weights.{p.agent_name}",
            p.current_weight, p.proposed_weight,
            f"hermes: win_rate={p.win_rate:.2f} n={p.total_signals}",
        )

    async def _queue_for_approval(self, p: WeightProposal) -> None:
        change_pct = round(p.change_pct, 2)
        await self.db.execute(
            "INSERT INTO optimizer_proposals "
            "(agent, regime, param_name, current_value, proposed_value, change_pct, reason, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')",
            p.agent_name, p.regime,
            f"aggregator.agent_weights.{p.agent_name}",
            p.current_weight, p.proposed_weight, change_pct,
            f"hermes: win_rate={p.win_rate:.2f} n={p.total_signals}",
        )
        await self.bus.publish("optimizer.proposal", {
            "source": "hermes",
            "agent": p.agent_name,
            "regime": p.regime,
            "param": f"aggregator.agent_weights.{p.agent_name}",
            "current": p.current_weight,
            "proposed": p.proposed_weight,
            "change_pct": change_pct,
        })

    async def _llm_summary(
        self,
        num_groups: int,
        auto_proposals: list[WeightProposal],
        pending_proposals: list[WeightProposal],
    ) -> str:
        if not auto_proposals and not pending_proposals:
            return f"Analyzed {num_groups} agent/regime groups. No weight changes needed this cycle."

        parts = [f"Analyzed {num_groups} agent/regime performance groups."]
        if auto_proposals:
            examples = ", ".join(
                f"{p.agent_name}/{p.regime} {p.current_weight:.2f}→{p.proposed_weight:.2f} (wr={p.win_rate:.0%})"
                for p in auto_proposals[:3]
            )
            parts.append(f"Auto-applied {len(auto_proposals)} weight change(s): {examples}.")
        if pending_proposals:
            parts.append(f"{len(pending_proposals)} larger change(s) queued for CIO approval.")

        prompt = (
            "You are Hermes, the self-improvement agent for an AI hedge fund. "
            + " ".join(parts)
            + " Write a 1-2 sentence CIO briefing."
        )
        try:
            return await self.router.chat("hermes", [{"role": "user", "content": prompt}])
        except Exception as exc:
            self.logger.warning("llm_summary_failed", error=str(exc))
            return " ".join(parts)

    def _load_yaml(self) -> dict:
        if not os.path.exists(self.params_path):
            return {}
        with open(self.params_path) as f:
            return yaml.safe_load(f) or {}

    def _save_yaml(self, data: dict) -> None:
        with open(self.params_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
