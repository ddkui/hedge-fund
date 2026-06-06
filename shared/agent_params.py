# shared/agent_params.py
"""
Reads per-agent, per-regime parameters from agent_params.yaml.
Falls back to provided defaults if file doesn't exist or key is missing.
"""
import os
from typing import Any


def load_agent_params(agent_name: str, regime: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """Load parameters for agent_name in the given regime from agent_params.yaml."""
    try:
        import yaml
        path = os.path.join(os.getcwd(), "agent_params.yaml")
        if not os.path.exists(path):
            return defaults
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        agent_section = data.get(agent_name, {})
        params = agent_section.get(regime) or agent_section.get("_default") or {}
        return {**defaults, **params}
    except Exception:
        return defaults
