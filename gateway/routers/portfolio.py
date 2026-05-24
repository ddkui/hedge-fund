# gateway/routers/portfolio.py
from fastapi import APIRouter, Depends
from shared.db import Database
from shared.config import settings
from gateway.deps import get_db

router = APIRouter()


@router.get("")
async def get_portfolio(db: Database = Depends(get_db)):
    row = await db.fetchrow(
        "SELECT cash, total_value, peak_value, open_positions, time "
        "FROM portfolio_state ORDER BY time DESC LIMIT 1"
    )
    if not row:
        return {
            "cash": settings.initial_capital,
            "total_value": settings.initial_capital,
            "peak_value": settings.initial_capital,
            "open_positions": 0,
            "time": None,
        }
    return dict(row)


@router.get("/positions")
async def get_positions(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY entry_time DESC"
    )
    return rows


@router.get("/trades")
async def get_trades(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM trades ORDER BY time DESC LIMIT $1", limit
    )
    return rows
