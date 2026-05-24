# gateway/routers/signals.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("")
async def get_signals(limit: int = 100, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM signals ORDER BY time DESC LIMIT $1", limit
    )
    return rows


@router.get("/{symbol}")
async def get_signals_for_symbol(symbol: str, limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM signals WHERE symbol = $1 ORDER BY time DESC LIMIT $2",
        symbol.upper(), limit,
    )
    return rows
