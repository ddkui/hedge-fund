"""
Hermes coder: generates targeted code improvement proposals for underperforming
analysis agents. Reads agent source + recent research insights, asks the LLM
for a minimal fix, stores proposals in hermes_patches for CIO review.

Only touches analysis agents — never execution/risk/portfolio_mgr.
"""
import json
import os
from pathlib import Path

from agents.hermes.models import CodePatch

_CODEABLE_AGENTS = {
    "technical":     "agents/technical/agent.py",
    "sentiment":     "agents/sentiment/agent.py",
    "macro":         "agents/macro/agent.py",
    "research":      "agents/research/agent.py",
    "vwap":          "agents/quant/vwap/agent.py",
    "news_momentum": "agents/quant/news_momentum/agent.py",
    "supply_demand": "agents/quant/supply_demand/agent.py",
}

_INSTRUCTIONS_PATH = "hermes_instructions.json"
_MAX_SOURCE_CHARS = 4000
_MAX_PATCHES_PER_CYCLE = 2


def load_instructions() -> list[str]:
    try:
        with open(_INSTRUCTIONS_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_instructions(instructions: list[str]) -> None:
    with open(_INSTRUCTIONS_PATH, "w") as f:
        json.dump(instructions, f, indent=2)


async def _fetch_research_hints(db, agent_name: str) -> str:
    """Pull recent implementation ideas from maintainer_researcher findings."""
    try:
        rows = await db.fetch(
            """
            SELECT title, implementation_idea FROM system_improvements
            WHERE lower(title) LIKE $1 OR lower(implementation_idea) LIKE $1
            ORDER BY combined_score DESC LIMIT 3
            """,
            f"%{agent_name.replace('_', ' ')}%",
        )
        if not rows:
            return ""
        ideas = "\n".join(
            f"- {r['title']}: {r['implementation_idea'][:200]}" for r in rows
        )
        return f"\nRecent research hints:\n{ideas}\n"
    except Exception:
        return ""


async def generate_patches(
    db,
    router,
    underperformers: list[dict],
    logger,
) -> list[CodePatch]:
    """
    For the worst-performing codeable agents, propose a minimal code fix.
    Returns at most _MAX_PATCHES_PER_CYCLE patches.
    """
    instructions = load_instructions()
    patches: list[CodePatch] = []

    candidates = [
        r for r in underperformers
        if r["agent"] in _CODEABLE_AGENTS and float(r["win_rate"]) < 0.50
    ]
    candidates.sort(key=lambda r: float(r["win_rate"]))

    for row in candidates[:_MAX_PATCHES_PER_CYCLE]:
        agent = row["agent"]
        file_path = _CODEABLE_AGENTS[agent]

        if not os.path.exists(file_path):
            continue

        original = Path(file_path).read_text(encoding="utf-8")
        research = await _fetch_research_hints(db, agent)
        instruction_block = ""
        if instructions:
            instruction_block = "\nCIO instructions:\n" + "\n".join(
                f"- {i}" for i in instructions
            )

        prompt = (
            f"You are Hermes, a self-improving AI hedge fund agent.\n"
            f"Agent '{agent}' has win_rate={float(row['win_rate']):.0%} "
            f"in '{row['regime']}' regime — needs improvement.\n\n"
            f"Source ({file_path}):\n```python\n{original[:_MAX_SOURCE_CHARS]}\n```\n"
            f"{research}{instruction_block}\n\n"
            "Return the COMPLETE improved Python file with ONE targeted fix.\n"
            "Rules:\n"
            "- Minimal change only — fix the root cause, not cosmetics\n"
            "- Keep all class names, method signatures, and imports unchanged\n"
            "- Add a one-line comment on changed line(s) explaining the fix\n"
            "- No new external dependencies\n"
            "- Return ONLY the Python code, no markdown fences or prose"
        )

        try:
            result = await router.chat("hermes", [{"role": "user", "content": prompt}])
            if "class " not in result or "def run_once" not in result:
                logger.warning("coder_invalid_output", agent=agent)
                continue
            patches.append(CodePatch(
                agent_name=agent,
                file_path=file_path,
                description=f"Improve {agent} win rate (currently {float(row['win_rate']):.0%})",
                original_content=original,
                patched_content=result.strip(),
                regime=row["regime"],
                win_rate=float(row["win_rate"]),
                reason=f"win_rate={float(row['win_rate']):.2f} n={row['total']}",
            ))
        except Exception as exc:
            logger.warning("coder_llm_failed", agent=agent, error=str(exc))

    return patches


async def save_patches(db, patches: list[CodePatch]) -> None:
    for p in patches:
        await db.execute(
            """
            INSERT INTO hermes_patches
                (agent_name, regime, win_rate, file_path, description,
                 original_content, patched_content, reason, status)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending')
            """,
            p.agent_name, p.regime, p.win_rate, p.file_path, p.description,
            p.original_content, p.patched_content, p.reason,
        )


async def apply_patch(db, patch_id: int) -> dict:
    """Apply a pending patch to disk and mark it applied in the DB."""
    row = await db.fetchrow(
        "SELECT * FROM hermes_patches WHERE id=$1 AND status='pending'", patch_id
    )
    if not row:
        return {"ok": False, "error": "Patch not found or already actioned"}

    try:
        Path(row["file_path"]).write_text(row["patched_content"], encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    await db.execute(
        "UPDATE hermes_patches SET status='applied', applied_at=NOW() WHERE id=$1",
        patch_id,
    )
    return {"ok": True, "file": row["file_path"]}
