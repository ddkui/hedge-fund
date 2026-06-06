# gateway/routers/analytics.py
import math
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()

RANGE_MAP = {
    "1d":  "1 day",
    "7d":  "7 days",
    "1m":  "30 days",
    "3m":  "90 days",
    "all": "36500 days",
}


def _range_interval(range_str: str) -> str:
    return RANGE_MAP.get(range_str, "7 days")


def _compute_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    variance = sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
    std = math.sqrt(variance) if variance > 0 else 0.0
    return round((mean / std) * math.sqrt(252), 4) if std > 0 else 0.0


def _compute_sortino(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    neg = [r for r in daily_returns if r < 0]
    if not neg:
        return 0.0
    downside_var = sum(r ** 2 for r in neg) / len(neg)
    downside_std = math.sqrt(downside_var)
    return round((mean / downside_std) * math.sqrt(252), 4) if downside_std > 0 else 0.0


def _compute_max_drawdown(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd, 6)


def _compute_drawdown_series(values: list[float]) -> list[float]:
    peak = values[0] if values else 1.0
    result = []
    for v in values:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        result.append(round(-dd * 100, 4))
    return result


def _compute_daily_returns(values: list[float]) -> list[float]:
    if len(values) < 2:
        return []
    return [
        round((values[i] - values[i - 1]) / values[i - 1] * 100, 4)
        for i in range(1, len(values))
    ]


@router.get("/summary")
async def get_summary(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    rows = await db.fetch(
        f"SELECT time, total_value FROM portfolio_state "
        f"WHERE time > now() - INTERVAL '{interval}' ORDER BY time ASC"
    )
    trades = await db.fetch(
        f"SELECT symbol, action, quantity, price, entry_price FROM trades "
        f"WHERE status = 'executed' AND time > now() - INTERVAL '{interval}'"
    )
    values = [float(r["total_value"]) for r in rows]
    if len(values) < 2:
        return {"error": "insufficient_data"}

    daily_returns = _compute_daily_returns(values)
    pnls = [
        (float(t["price"]) - float(t["entry_price"])) * float(t["quantity"])
        * (1 if t["action"] == "long" else -1)
        for t in trades
    ]
    wins = sum(1 for p in pnls if p > 0)
    start_val = values[0]
    end_val = values[-1]
    days = max((datetime.fromisoformat(str(rows[-1]["time"])) -
                datetime.fromisoformat(str(rows[0]["time"]))).days, 1)
    cagr = round(((end_val / start_val) ** (365 / days) - 1) * 100, 4) if start_val > 0 else 0.0

    return {
        "sharpe": _compute_sharpe(daily_returns),
        "sortino": _compute_sortino(daily_returns),
        "max_drawdown": round(_compute_max_drawdown(values) * 100, 4),
        "win_rate": round(wins / len(pnls), 4) if pnls else 0.0,
        "total_pnl": round(sum(pnls), 2),
        "trade_count": len(trades),
        "cagr": cagr,
        "start_value": start_val,
        "end_value": end_val,
    }


@router.get("/equity-curve")
async def get_equity_curve(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    rows = await db.fetch(
        f"SELECT time, total_value FROM portfolio_state "
        f"WHERE time > now() - INTERVAL '{interval}' ORDER BY time ASC"
    )
    times = [str(r["time"]) for r in rows]
    values = [float(r["total_value"]) for r in rows]
    daily_returns = _compute_daily_returns(values)
    drawdown = _compute_drawdown_series(values)
    return {
        "labels": times,
        "equity": values,
        "daily_returns": [0.0] + daily_returns,
        "drawdown": drawdown,
    }


@router.get("/pnl-by-symbol")
async def get_pnl_by_symbol(range: str = Query("7d"), db: Database = Depends(get_db)):
    interval = _range_interval(range)
    trades = await db.fetch(
        f"SELECT symbol, action, quantity, price, entry_price FROM trades "
        f"WHERE status = 'executed' AND time > now() - INTERVAL '{interval}'"
    )
    by_symbol: dict[str, float] = {}
    for t in trades:
        pnl = (float(t["price"]) - float(t["entry_price"])) * float(t["quantity"])
        if t["action"] == "short":
            pnl = -pnl
        by_symbol[t["symbol"]] = by_symbol.get(t["symbol"], 0.0) + pnl
    result = [{"symbol": s, "pnl": round(p, 2)} for s, p in by_symbol.items()]
    return sorted(result, key=lambda x: x["pnl"], reverse=True)


@router.get("/monthly-returns")
async def get_monthly_returns(db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT time, total_value FROM portfolio_state ORDER BY time ASC"
    )
    if not rows:
        return []
    monthly: dict[tuple, list[float]] = {}
    for r in rows:
        t = datetime.fromisoformat(str(r["time"]).replace("+00:00", "+00:00"))
        key = (t.year, t.month)
        monthly.setdefault(key, []).append(float(r["total_value"]))
    result = []
    for (year, month), vals in sorted(monthly.items()):
        ret = round((vals[-1] - vals[0]) / vals[0] * 100, 4) if vals[0] > 0 else 0.0
        result.append({"year": year, "month": month, "return_pct": ret})
    return result
