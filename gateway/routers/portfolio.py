# gateway/routers/portfolio.py
from fastapi import APIRouter, Depends
from shared.db import Database
from shared.config import settings
from gateway.deps import get_db

router = APIRouter()


@router.get("")
async def get_portfolio(db: Database = Depends(get_db)):
    state = await db.fetchrow(
        "SELECT cash, total_value, peak_value, open_positions, time "
        "FROM portfolio_state ORDER BY time DESC LIMIT 1"
    )

    cash = float(state["cash"]) if state else settings.initial_capital
    peak_value = float(state["peak_value"]) if state else settings.initial_capital
    recorded_time = state["time"] if state else None

    # Mark-to-market: sum open position values at current prices
    open_positions = await db.fetch(
        "SELECT symbol, direction, quantity, entry_price FROM positions WHERE status = 'open'"
    )

    positions_value = 0.0
    if open_positions:
        symbols = list({p["symbol"] for p in open_positions})
        price_rows = await db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices "
            "WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            symbols,
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        for pos in open_positions:
            symbol = pos["symbol"]
            qty = float(pos["quantity"])
            current_price = prices.get(symbol, float(pos["entry_price"]))
            if pos["direction"] == "short":
                # Short: profit = entry - current; value = 2*entry - current per unit
                entry = float(pos["entry_price"])
                positions_value += qty * (2 * entry - current_price)
            else:
                positions_value += qty * current_price

    total_value = cash + positions_value
    peak_value = max(peak_value, total_value)

    return {
        "cash": round(cash, 2),
        "total_value": round(total_value, 2),
        "peak_value": round(peak_value, 2),
        "open_positions": len(open_positions),
        "time": recorded_time,
    }


@router.get("/positions")
async def get_positions(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM positions WHERE status = 'open' ORDER BY entry_time DESC"
    )
    # Enrich with current prices for unrealized P&L
    if not rows:
        return []

    symbols = list({r["symbol"] for r in rows})
    price_rows = await db.fetch(
        "SELECT DISTINCT ON (symbol) symbol, close FROM prices "
        "WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
        symbols,
    )
    prices = {r["symbol"]: float(r["close"]) for r in price_rows}

    result = []
    for row in rows:
        pos = dict(row)
        symbol = pos["symbol"]
        qty = float(pos["quantity"])
        entry = float(pos["entry_price"])
        current = prices.get(symbol, entry)
        multiplier = -1.0 if pos["direction"] == "short" else 1.0
        unrealized_pnl = (current - entry) * qty * multiplier
        pos["current_price"] = round(current, 4)
        pos["unrealized_pnl"] = round(unrealized_pnl, 2)
        pos["unrealized_pnl_pct"] = round((unrealized_pnl / (entry * qty)) * 100, 2) if entry * qty > 0 else 0.0
        result.append(pos)
    return result


@router.get("/trades")
async def get_trades(limit: int = 100, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM trades ORDER BY time DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]
