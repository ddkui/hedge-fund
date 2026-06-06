# gateway/routers/brokers.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/status")
async def broker_status(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (broker_name)
            broker_name, status, fill_price, time
        FROM broker_fills
        ORDER BY broker_name, time DESC
        """
    )
    return [dict(r) for r in rows]


@router.get("/fills")
async def broker_fills(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM broker_fills ORDER BY time DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]
