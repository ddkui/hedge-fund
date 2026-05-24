# gateway/routers/backtests.py
from fastapi import APIRouter, Depends, HTTPException
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/algos")
async def get_algos(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM quant_algos ORDER BY created_at DESC"
    )
    return rows


@router.get("/algos/{algo_id}")
async def get_algo(algo_id: int, db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT * FROM quant_algos WHERE id = $1", algo_id
    )
    if not row:
        raise HTTPException(status_code=404, detail="Algo not found")
    return row
