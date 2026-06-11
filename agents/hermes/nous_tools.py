"""
Registers hedge fund tools in the Nous Hermes tool registry.

All handlers are synchronous. Write-backs are deferred to state lists
and flushed async by NousBridge after run_conversation() returns.
YAML writes happen inline (plain file I/O, no async needed).
"""
import json
import threading
import yaml
from pathlib import Path

# Single source of truth — don't redefine here
from agents.hermes.coder import _CODEABLE_AGENTS


def register_hedge_fund_tools(
    registry, state: dict, lock: threading.Lock, params_path: str
) -> None:
    """Register all hedge fund tools under toolset='hedge_fund'."""

    # ── get_win_rates ──────────────────────────────────────────────────────
    def _handle_get_win_rates(args, **kw) -> str:
        return json.dumps(state["win_rates"])

    registry.register(
        name="get_win_rates",
        toolset="hedge_fund",
        schema={
            "name": "get_win_rates",
            "description": (
                "Returns per-agent win rates by market regime for the last 30 days. "
                "JSON array of {agent, regime, wins, total, win_rate}."
            ),
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        handler=_handle_get_win_rates,
        override=True,
    )

    # ── get_weights ────────────────────────────────────────────────────────
    def _handle_get_weights(args, **kw) -> str:
        regime = args.get("regime", "")
        agg = state["yaml_data"].get("aggregator", {})
        if regime:
            weights = agg.get(regime, {}).get("agent_weights", {})
        else:
            weights = {
                r: s.get("agent_weights", {})
                for r, s in agg.items()
                if not r.startswith("_")
            }
        return json.dumps(weights)

    registry.register(
        name="get_weights",
        toolset="hedge_fund",
        schema={
            "name": "get_weights",
            "description": "Get current aggregator agent_weights from agent_params.yaml.",
            "parameters": {
                "type": "object",
                "properties": {
                    "regime": {
                        "type": "string",
                        "description": "Regime (expansion/contraction/crisis/pandemic). Omit for all.",
                    }
                },
                "required": [],
            },
        },
        handler=_handle_get_weights,
        override=True,
    )

    # ── update_weight ──────────────────────────────────────────────────────
    def _handle_update_weight(args, **kw) -> str:
        regime = args.get("regime", "")
        agent = args.get("agent", "")
        try:
            weight = round(float(args.get("weight", 0)), 3)
        except (TypeError, ValueError):
            return json.dumps({"error": "weight must be a number"})
        if weight < 0.1 or weight > 2.5:
            return json.dumps({"error": "weight must be between 0.1 and 2.5"})
        with lock:
            agg = state["yaml_data"].get("aggregator", {})
            section = agg.get(regime)
            if not section or "agent_weights" not in section:
                return json.dumps({"error": f"regime '{regime}' not found"})
            if agent not in section["agent_weights"]:
                return json.dumps({"error": f"agent '{agent}' not in regime '{regime}'"})
            old = section["agent_weights"][agent]
            section["agent_weights"][agent] = weight
            with open(params_path, "w") as f:
                yaml.dump(state["yaml_data"], f, default_flow_style=False, allow_unicode=True)
            state["applied"].append({
                "agent": agent, "regime": regime,
                "old_value": old, "new_value": weight,
                "reason": args.get("reason", "hermes-nous: direct adjustment"),
            })
        return json.dumps({"ok": True, "agent": agent, "regime": regime, "old": old, "new": weight})

    registry.register(
        name="update_weight",
        toolset="hedge_fund",
        schema={
            "name": "update_weight",
            "description": (
                "Directly update an aggregator weight (<10% change). "
                "For larger changes use queue_weight_proposal."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "regime": {"type": "string"},
                    "agent": {"type": "string"},
                    "weight": {"type": "number", "description": "New weight (0.1–2.5)"},
                    "reason": {"type": "string"},
                },
                "required": ["regime", "agent", "weight"],
            },
        },
        handler=_handle_update_weight,
        override=True,
    )

    # ── queue_weight_proposal ──────────────────────────────────────────────
    def _handle_queue_proposal(args, **kw) -> str:
        try:
            current = float(args.get("current_weight", 0))
            proposed = float(args.get("proposed_weight", 0))
        except (TypeError, ValueError):
            return json.dumps({"error": "weights must be numbers"})
        with lock:
            state["proposals"].append({
                "agent": args.get("agent", ""),
                "regime": args.get("regime", ""),
                "current_value": current,
                "proposed_value": proposed,
                "reason": args.get("reason", "hermes-nous"),
            })
        return json.dumps({"ok": True, "queued": True})

    registry.register(
        name="queue_weight_proposal",
        toolset="hedge_fund",
        schema={
            "name": "queue_weight_proposal",
            "description": "Queue a weight change for CIO approval (change ≥10%).",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent": {"type": "string"},
                    "regime": {"type": "string"},
                    "current_weight": {"type": "number"},
                    "proposed_weight": {"type": "number"},
                    "reason": {"type": "string"},
                },
                "required": ["agent", "regime", "current_weight", "proposed_weight", "reason"],
            },
        },
        handler=_handle_queue_proposal,
        override=True,
    )

    # ── read_agent_code ────────────────────────────────────────────────────
    def _handle_read_agent_code(args, **kw) -> str:
        agent_name = args.get("agent_name", "")
        path = _CODEABLE_AGENTS.get(agent_name)
        if not path:
            return json.dumps({
                "error": f"'{agent_name}' is not codeable",
                "codeable_agents": list(_CODEABLE_AGENTS),
            })
        p = Path(path)
        if not p.exists():
            return json.dumps({"error": f"file not found: {path}"})
        return p.read_text(encoding="utf-8")[:4000]

    registry.register(
        name="read_agent_code",
        toolset="hedge_fund",
        schema={
            "name": "read_agent_code",
            "description": "Read an analysis agent's source code. Call before propose_code_patch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": f"One of: {', '.join(_CODEABLE_AGENTS)}",
                    }
                },
                "required": ["agent_name"],
            },
        },
        handler=_handle_read_agent_code,
        override=True,
    )

    # ── propose_code_patch ─────────────────────────────────────────────────
    def _handle_propose_patch(args, **kw) -> str:
        agent_name = args.get("agent_name", "")
        if agent_name not in _CODEABLE_AGENTS:
            return json.dumps({"error": f"'{agent_name}' is not codeable"})
        patched = args.get("patched_code", "")
        if "class " not in patched or "def run_once" not in patched:
            return json.dumps({"error": "patched_code must contain 'class' and 'def run_once'"})
        file_path = _CODEABLE_AGENTS[agent_name]
        original = Path(file_path).read_text(encoding="utf-8") if Path(file_path).exists() else ""
        win_rate = next(
            (float(r["win_rate"]) for r in state["win_rates"] if r["agent"] == agent_name),
            0.0,
        )
        with lock:
            if len(state["patches"]) >= 2:
                return json.dumps({"error": "patch limit (2) reached for this cycle"})
            state["patches"].append({
                "agent_name": agent_name,
                "file_path": file_path,
                "description": args.get("description", f"Improve {agent_name} win rate"),
                "original_content": original,
                "patched_content": patched,
                "regime": args.get("regime", ""),
                "win_rate": win_rate,
                "reason": args.get("reason", "hermes-nous"),
            })
        return json.dumps({"ok": True, "status": "queued_for_cio_review", "agent": agent_name})

    registry.register(
        name="propose_code_patch",
        toolset="hedge_fund",
        schema={
            "name": "propose_code_patch",
            "description": (
                "Propose a code improvement for an underperforming agent. "
                "Queued for CIO review — NOT applied automatically. "
                "Call read_agent_code first. Return the COMPLETE improved Python file."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {"type": "string"},
                    "patched_code": {"type": "string", "description": "Complete improved Python file"},
                    "description": {"type": "string"},
                    "regime": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["agent_name", "patched_code", "description", "reason"],
            },
        },
        handler=_handle_propose_patch,
        override=True,
    )
