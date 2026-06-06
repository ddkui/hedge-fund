# gateway/routers/intelligence.py
import yaml
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from shared.db import Database
from shared.bus import RedisBus
from gateway.deps import get_db, get_bus

router = APIRouter()


@router.get("/status")
async def get_status(bus: RedisBus = Depends(get_bus)):
    data = await bus.get("alpha:status") or {
        "tier": "learning", "sharpe": 0.0, "jensens_alpha": 0.0,
        "beta": 1.0, "portfolio_annual_pct": 0.0, "spy_annual_pct": 0.0,
    }
    return data


@router.get("/accuracy")
async def get_accuracy(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT agent,
               count(*) as signals,
               round(avg(CASE WHEN was_correct THEN 1.0 ELSE 0.0 END)::numeric, 4) as accuracy,
               round(avg(pnl)::numeric, 2) as avg_pnl
        FROM signal_outcomes
        WHERE time > now() - INTERVAL '30 days' AND was_correct IS NOT NULL
        GROUP BY agent
        ORDER BY accuracy DESC
        """
    )
    return [dict(r) for r in rows]


@router.get("/params")
async def get_params(regime: str = "expansion"):
    try:
        with open("agent_params.yaml") as f:
            data = yaml.safe_load(f) or {}
        result = {}
        for agent_name, regimes in data.items():
            if agent_name.startswith("_"):
                continue
            result[agent_name] = regimes.get(regime) or regimes.get("_default") or {}
        return {"regime": regime, "params": result}
    except FileNotFoundError:
        return {"regime": regime, "params": {}}


@router.get("/proposals")
async def get_proposals(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM optimizer_proposals WHERE status = 'pending' ORDER BY time DESC"
    )
    return [dict(r) for r in rows]


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(proposal_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT * FROM optimizer_proposals WHERE id = $1", proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    try:
        with open("agent_params.yaml") as f:
            params = yaml.safe_load(f) or {}
        params.setdefault(row["agent"], {}).setdefault(row["regime"], {})[row["param_name"]] = row["proposed_value"]
        with open("agent_params.yaml", "w") as f:
            yaml.dump(params, f, default_flow_style=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to apply: {exc}")
    await db.execute(
        "UPDATE optimizer_proposals SET status='approved', reviewed_at=now(), reviewed_by='dashboard' WHERE id=$1",
        proposal_id
    )
    await db.execute(
        "INSERT INTO optimizer_history (agent, regime, param_name, old_value, new_value, reason, auto_applied) "
        "VALUES ($1,$2,$3,$4,$5,$6,FALSE)",
        row["agent"], row["regime"], row["param_name"],
        row["current_value"], row["proposed_value"], "Approved via dashboard",
    )
    return {"status": "approved", "id": proposal_id}


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(proposal_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id FROM optimizer_proposals WHERE id = $1", proposal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Proposal not found")
    await db.execute(
        "UPDATE optimizer_proposals SET status='rejected', reviewed_at=now(), reviewed_by='dashboard' WHERE id=$1",
        proposal_id
    )
    return {"status": "rejected", "id": proposal_id}


@router.get("/history")
async def get_history(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM optimizer_history ORDER BY time DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]


@router.get("/strategies")
async def get_strategies():
    strategy_dir = Path("memory/obsidian/alpha_monitor")
    if not strategy_dir.exists():
        return []
    files = sorted(strategy_dir.glob("*.md"), reverse=True)
    return [{"filename": f.name, "content": f.read_text(encoding="utf-8")} for f in files[:10]]
