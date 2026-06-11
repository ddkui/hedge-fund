"""
NousBridge — embeds Nous Hermes AIAgent in the hedge fund's asyncio loop.

Three embedding concerns and their fixes:
  1. Async: run_conversation() is sync → asyncio.to_thread(), never blocks loop.
  2. Session isolation: skip_memory=True + unique session_id per cycle.
  3. Tool discovery: tools registered under toolset='hedge_fund';
     enabled_toolsets=['hedge_fund'] + disabled_toolsets=[...built-ins...]

Opt-in via env var NOUS_ENABLED=1. Falls back to the rule-based analyzer
when unset, package missing, or agent errors.
"""
import asyncio
import datetime
import os
import threading
import uuid
import yaml
from typing import Any

from agents.hermes import analyzer, coder, nous_tools
from agents.hermes.models import WeightProposal

# Belt-and-suspenders: explicitly disable all known built-in toolsets
_BUILTIN_TOOLSETS = [
    "file", "web", "terminal", "bash", "search", "vision",
    "computer_use", "mcp", "cron", "memory", "pty",
]

_CODE_CYCLE_INTERVAL = datetime.timedelta(hours=24)

_CYCLE_PROMPT = """\
You are Hermes, the self-improvement meta-agent for an AI hedge fund.

Your mission each hourly cycle:
1. Call get_win_rates() to see per-agent performance across market regimes.
2. Call get_weights() to see current aggregator weights.
3. For each agent/regime with ≥10 outcomes:
   - win_rate < 0.45 → reduce weight ~5%. Change <10%: use update_weight.
     Change ≥10%: use queue_weight_proposal for CIO approval.
   - win_rate ≥ 0.70 → increase weight ~5%. Same threshold rule.
4. For at most 2 agents with win_rate < 0.50: call read_agent_code() then
   propose_code_patch() with a targeted, minimal fix. Patches require CIO
   approval before being written to disk.

Rules:
- Weight range: 0.1–2.5. Step: ~5%. Min 10 outcomes before any change.
- Code patches must preserve class names, signatures, and imports.
- End with a 1–2 sentence CIO summary of actions taken.
"""


class NousBridge:
    """
    Runs Nous Hermes AIAgent in a worker thread and bridges write-backs
    to the hedge fund's asyncio event loop.
    """

    def __init__(self, db, bus, router, logger, params_path: str = "agent_params.yaml"):
        self.db = db
        self.bus = bus
        self.router = router
        self.logger = logger
        self.params_path = params_path
        self._last_code_cycle: datetime.datetime | None = None

    async def run_cycle(self) -> dict[str, Any]:
        """Entry point called by HermesAgent.run_once()."""
        if not os.getenv("NOUS_ENABLED"):
            return await self._rule_based_cycle()
        try:
            return await self._nous_cycle()
        except Exception as exc:
            self.logger.warning("nous_fallback", error=str(exc))
            return await self._rule_based_cycle()

    # ── Nous path ─────────────────────────────────────────────────────────

    async def _nous_cycle(self) -> dict[str, Any]:
        stats = await analyzer.collect_win_rates(self.db)
        win_rates = _rows_to_dicts(stats)
        yaml_data = _load_yaml(self.params_path)

        state: dict[str, Any] = {
            "win_rates": win_rates,
            "yaml_data": yaml_data,
            "applied": [],
            "proposals": [],
            "patches": [],
        }
        lock = threading.Lock()

        summary = await asyncio.to_thread(self._run_agent_sync, state, lock)
        await self._flush_writes(state)

        return {
            "outcomes_analyzed": sum(int(r["total"]) for r in win_rates),
            "weights_applied": len(state["applied"]),
            "proposals_queued": len(state["proposals"]),
            "patches_queued": len(state["patches"]),
            "summary": summary,
        }

    def _run_agent_sync(self, state: dict, lock: threading.Lock) -> str:
        from agent.agent import AIAgent          # raises ImportError if not installed
        from tools.registry import registry

        nous_tools.register_hedge_fund_tools(registry, state, lock, self.params_path)

        _PREFERRED_KWARGS = dict(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("HERMES_API_KEY", "ollama"),
            model=os.getenv("HERMES_MODEL", "nous-hermes2"),
            max_iterations=20,
            enabled_toolsets=["hedge_fund"],
            disabled_toolsets=_BUILTIN_TOOLSETS,
            quiet_mode=True,
            session_id=f"hedge_fund_{uuid.uuid4().hex}",
        )
        _OPTIONAL_KWARGS = dict(
            skip_memory=True,
            load_soul_identity=False,
            skip_context_files=True,
        )
        try:
            agent = AIAgent(**_PREFERRED_KWARGS, **_OPTIONAL_KWARGS)
        except TypeError:
            # Version doesn't support some optional kwargs — use minimal set
            agent = AIAgent(**_PREFERRED_KWARGS)

        return agent.run_conversation(_CYCLE_PROMPT)

    # ── Rule-based fallback ────────────────────────────────────────────────

    async def _rule_based_cycle(self) -> dict[str, Any]:
        stats = await analyzer.collect_win_rates(self.db)
        yaml_data = _load_yaml(self.params_path)
        proposals = analyzer.compute_weight_proposals(stats, yaml_data)

        auto = [p for p in proposals if p.auto_apply]
        pending = [p for p in proposals if not p.auto_apply]

        if auto:
            analyzer.apply_yaml_proposals(yaml_data, auto)
            _save_yaml(yaml_data, self.params_path)
            for p in auto:
                await self._record_applied(p)

        for p in pending:
            await self._queue_proposal(p)

        patches_saved = 0
        now = datetime.datetime.now(datetime.timezone.utc)
        if self._last_code_cycle is None or now - self._last_code_cycle >= _CODE_CYCLE_INTERVAL:
            patches = await coder.generate_patches(self.db, self.router, stats, self.logger)
            if patches:
                await coder.save_patches(self.db, patches)
                patches_saved = len(patches)
            self._last_code_cycle = now

        total = sum(int(r["total"]) for r in stats)
        summary = _rule_summary(len(stats), auto, pending)
        return {
            "outcomes_analyzed": total,
            "weights_applied": len(auto),
            "proposals_queued": len(pending),
            "patches_queued": patches_saved,
            "summary": summary,
        }

    async def _record_applied(self, p: WeightProposal) -> None:
        await self.db.execute(
            "INSERT INTO optimizer_history "
            "(agent, regime, param_name, old_value, new_value, reason, auto_applied) "
            "VALUES ($1,$2,$3,$4,$5,$6,TRUE)",
            p.agent_name, p.regime,
            f"aggregator.agent_weights.{p.agent_name}",
            p.current_weight, p.proposed_weight,
            f"hermes: win_rate={p.win_rate:.2f} n={p.total_signals}",
        )

    async def _queue_proposal(self, p: WeightProposal) -> None:
        await self.db.execute(
            "INSERT INTO optimizer_proposals "
            "(agent, regime, param_name, current_value, proposed_value, change_pct, reason, status) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,'pending')",
            p.agent_name, p.regime,
            f"aggregator.agent_weights.{p.agent_name}",
            p.current_weight, p.proposed_weight, round(p.change_pct, 2),
            f"hermes: win_rate={p.win_rate:.2f} n={p.total_signals}",
        )
        await self.bus.publish("optimizer.proposal", {
            "source": "hermes",
            "agent": p.agent_name, "regime": p.regime,
            "current": p.current_weight, "proposed": p.proposed_weight,
        })

    # ── Nous write-back flush ──────────────────────────────────────────────

    async def _flush_writes(self, state: dict) -> None:
        for e in state["applied"]:
            await self.db.execute(
                "INSERT INTO optimizer_history "
                "(agent, regime, param_name, old_value, new_value, reason, auto_applied) "
                "VALUES ($1,$2,$3,$4,$5,$6,TRUE)",
                e["agent"], e["regime"],
                f"aggregator.agent_weights.{e['agent']}",
                e["old_value"], e["new_value"], e["reason"],
            )
        for p in state["proposals"]:
            current, proposed = p["current_value"], p["proposed_value"]
            change_pct = abs((proposed - current) / max(current, 1e-9)) * 100
            await self.db.execute(
                "INSERT INTO optimizer_proposals "
                "(agent, regime, param_name, current_value, proposed_value, "
                "change_pct, reason, status) "
                "VALUES ($1,$2,$3,$4,$5,$6,$7,'pending')",
                p["agent"], p["regime"],
                f"aggregator.agent_weights.{p['agent']}",
                current, proposed, round(change_pct, 2), p["reason"],
            )
        for patch in state["patches"]:
            await self.db.execute(
                """
                INSERT INTO hermes_patches
                    (agent_name, regime, win_rate, file_path, description,
                     original_content, patched_content, reason, status)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'pending')
                """,
                patch["agent_name"], patch["regime"], patch["win_rate"],
                patch["file_path"], patch["description"],
                patch["original_content"], patch["patched_content"], patch["reason"],
            )


# ── Helpers ────────────────────────────────────────────────────────────────

def _rows_to_dicts(rows) -> list[dict]:
    result = []
    for r in rows:
        total = int(r["total"])
        wins = int(r["wins"])
        result.append({
            "agent": r["agent"],
            "regime": r["regime"],
            "wins": wins,
            "total": total,
            "win_rate": round(wins / total, 4) if total else 0.0,
        })
    return result


def _load_yaml(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}


def _save_yaml(data: dict, path: str) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def _rule_summary(num_groups: int, auto: list, pending: list) -> str:
    if not auto and not pending:
        return f"Analyzed {num_groups} agent/regime groups. No changes needed."
    parts = [f"Analyzed {num_groups} groups."]
    if auto:
        ex = ", ".join(
            f"{p.agent_name}/{p.regime} {p.current_weight:.2f}→{p.proposed_weight:.2f}"
            for p in auto[:3]
        )
        parts.append(f"Auto-applied {len(auto)} change(s): {ex}.")
    if pending:
        parts.append(f"{len(pending)} larger change(s) queued for CIO approval.")
    return " ".join(parts)
