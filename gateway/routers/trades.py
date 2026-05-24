# gateway/routers/trades.py
from fastapi import APIRouter, Depends, HTTPException
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/pending")
async def get_pending_trades(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM trades WHERE status = 'pending' ORDER BY time DESC"
    )
    return rows


@router.post("/{trade_id}/approve")
async def approve_trade(trade_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id, status FROM trades WHERE id = $1", trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.execute(
        "UPDATE trades SET status = 'approved' WHERE id = $1", trade_id
    )
    return {"id": trade_id, "status": "approved"}


@router.post("/{trade_id}/deny")
async def deny_trade(trade_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow("SELECT id, status FROM trades WHERE id = $1", trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    await db.execute(
        "UPDATE trades SET status = 'denied' WHERE id = $1", trade_id
    )
    return {"id": trade_id, "status": "denied"}
