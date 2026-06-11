# gateway/routers/hermes.py
"""
Hermes dashboard API — win rates, aggregator weights, code patches,
custom instructions, and manual trigger.
"""
import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from shared.db import Database
from shared.bus import RedisBus
from gateway.deps import get_db, get_bus
from agents.hermes import analyzer, coder

router = APIRouter(prefix="/api/hermes", tags=["hermes"])

_PARAMS_PATH = "agent_params.yaml"


# ── Win rates ──────────────────────────────────────────────────────────────

@router.get("/win-rates")
async def get_win_rates(db: Database = Depends(get_db)):
    """Per-agent × per-regime win rates from the last 30 days."""
    rows = await db.fetch(
        """
        SELECT agent, regime,
               COUNT(*) FILTER (WHERE was_correct = TRUE)  AS wins,
               COUNT(*) FILTER (WHERE was_correct IS NOT NULL) AS total
        FROM signal_outcomes
        WHERE time > NOW() - INTERVAL '30 days' AND was_correct IS NOT NULL
        GROUP BY agent, regime
        ORDER BY agent, regime
        """
    )
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


# ── Aggregator weights ─────────────────────────────────────────────────────

@router.get("/weights")
async def get_weights():
    """Current aggregator weights for every regime from agent_params.yaml."""
    try:
        with open(_PARAMS_PATH) as f:
            data = yaml.safe_load(f) or {}
        agg = data.get("aggregator", {})
        return {
            regime: section.get("agent_weights", {})
            for regime, section in agg.items()
            if not regime.startswith("_")
        }
    except FileNotFoundError:
        return {}


class WeightUpdate(BaseModel):
    regime: str
    agent: str
    weight: float


@router.put("/weights")
async def update_weight(body: WeightUpdate):
    """Manually set an aggregator weight for a specific agent × regime."""
    if body.weight < 0.1 or body.weight > 2.5:
        raise HTTPException(status_code=400, detail="Weight must be between 0.1 and 2.5")
    try:
        with open(_PARAMS_PATH) as f:
            data = yaml.safe_load(f) or {}
        regime_section = data.get("aggregator", {}).get(body.regime)
        if not regime_section or "agent_weights" not in regime_section:
            raise HTTPException(status_code=404, detail=f"Regime '{body.regime}' not found")
        if body.agent not in regime_section["agent_weights"]:
            raise HTTPException(status_code=404, detail=f"Agent '{body.agent}' not in weights")
        regime_section["agent_weights"][body.agent] = round(body.weight, 3)
        with open(_PARAMS_PATH, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        return {"ok": True, "regime": body.regime, "agent": body.agent, "weight": body.weight}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Weight proposals ───────────────────────────────────────────────────────

@router.get("/proposals")
async def get_proposals(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM optimizer_proposals WHERE status='pending' AND reason LIKE 'hermes%' "
        "ORDER BY time DESC"
    )
    return [dict(r) for r in rows]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT * FROM optimizer_proposals WHERE id=$1 AND status='pending'", proposal_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        with open(_PARAMS_PATH) as f:
            params = yaml.safe_load(f) or {}
        parts = row["param_name"].split(".")
        regime_section = params.get("aggregator", {}).get(row["regime"])
        if regime_section and "agent_weights" in regime_section and len(parts) == 3:
            regime_section["agent_weights"][parts[2]] = float(row["proposed_value"])
        with open(_PARAMS_PATH, "w") as f:
            yaml.dump(params, f, default_flow_style=False, allow_unicode=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to apply: {exc}")
    await db.execute(
        "UPDATE optimizer_proposals SET status='approved', reviewed_at=NOW(), reviewed_by='dashboard' WHERE id=$1",
        proposal_id,
    )
    await db.execute(
        "INSERT INTO optimizer_history (agent, regime, param_name, old_value, new_value, reason, auto_applied) "
        "VALUES ($1,$2,$3,$4,$5,$6,FALSE)",
        row["agent"], row["regime"], row["param_name"],
        row["current_value"], row["proposed_value"], "Approved via Hermes dashboard",
    )
    return {"status": "approved", "id": proposal_id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id FROM optimizer_proposals WHERE id=$1", proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await db.execute(
        "UPDATE optimizer_proposals SET status='rejected', reviewed_at=NOW(), reviewed_by='dashboard' WHERE id=$1",
        proposal_id,
    )
    return {"status": "rejected", "id": proposal_id}


# ── Code patches ──────────────────────────────────────────────────────────

@router.get("/patches")
async def get_patches(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT id, time, agent_name, regime, win_rate, file_path, description, reason, status "
        "FROM hermes_patches ORDER BY time DESC LIMIT 50"
    )
    return [dict(r) for r in rows]


@router.get("/patches/{patch_id}")
async def get_patch_detail(patch_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT * FROM hermes_patches WHERE id=$1", patch_id)
    if not row:
        raise HTTPException(status_code=404, detail="Patch not found")
    return dict(row)


@router.post("/patches/{patch_id}/apply")
async def apply_patch(patch_id: int, db: Database = Depends(get_db)):
    result = await coder.apply_patch(db, patch_id)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/patches/{patch_id}/reject")
async def reject_patch(patch_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT id FROM hermes_patches WHERE id=$1 AND status='pending'", patch_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Patch not found or already actioned")
    await db.execute("UPDATE hermes_patches SET status='rejected' WHERE id=$1", patch_id)
    return {"status": "rejected", "id": patch_id}


# ── Instructions ──────────────────────────────────────────────────────────

@router.get("/instructions")
async def get_instructions():
    return coder.load_instructions()


class InstructionBody(BaseModel):
    text: str


@router.post("/instructions")
async def add_instruction(body: InstructionBody):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Instruction cannot be empty")
    instructions = coder.load_instructions()
    instructions.append(body.text.strip())
    coder.save_instructions(instructions)
    return instructions


@router.delete("/instructions/{idx}")
async def delete_instruction(idx: int):
    instructions = coder.load_instructions()
    if idx < 0 or idx >= len(instructions):
        raise HTTPException(status_code=404, detail="Index out of range")
    instructions.pop(idx)
    coder.save_instructions(instructions)
    return instructions


# ── Manual trigger ────────────────────────────────────────────────────────

@router.post("/trigger")
async def trigger_cycle(db: Database = Depends(get_db), bus: RedisBus = Depends(get_bus)):
    """Run a Hermes weight-proposal cycle immediately from the dashboard."""
    stats = await analyzer.collect_win_rates(db)
    try:
        with open(_PARAMS_PATH) as f:
            yaml_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        yaml_data = {}

    proposals = analyzer.compute_weight_proposals(stats, yaml_data)
    auto = [p for p in proposals if p.auto_apply]
    pending = [p for p in proposals if not p.auto_apply]

    if auto:
        analyzer.apply_yaml_proposals(yaml_data, auto)
        with open(_PARAMS_PATH, "w") as f:
            yaml.dump(yaml_data, f, default_flow_style=False, allow_unicode=True)
        for p in auto:
            await db.execute(
                "INSERT INTO optimizer_history "
                "(agent, regime, param_name, old_value, new_value, reason, auto_applied) "
                "VALUES ($1,$2,$3,$4,$5,$6,TRUE)",
                p.agent_name, p.regime,
                f"aggregator.agent_weights.{p.agent_name}",
                p.current_weight, p.proposed_weight,
                f"hermes-trigger: win_rate={p.win_rate:.2f}",
            )

    for p in pending:
        await db.execute(
            "INSERT INTO optimizer_proposals "
            "(agent, regime, param_name, current_value, proposed_value, change_pct, reason, status) "
            "VALUES ($1,$2,$3,$4,$5,$6,$7,'pending')",
            p.agent_name, p.regime,
            f"aggregator.agent_weights.{p.agent_name}",
            p.current_weight, p.proposed_weight, round(p.change_pct, 2),
            f"hermes-trigger: win_rate={p.win_rate:.2f}",
        )

    await bus.publish("ops.hermes", {
        "event": "manual_trigger",
        "auto_applied": len(auto),
        "queued": len(pending),
    })
    return {
        "agent_regimes_analyzed": len(stats),
        "auto_applied": len(auto),
        "queued_for_approval": len(pending),
    }
