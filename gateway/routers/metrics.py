# gateway/routers/metrics.py
import time
from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()

_cache: dict = {"data": None, "ts": 0.0}
CACHE_TTL = 15.0


async def _collect(db: Database) -> str:
    now = time.time()
    if _cache["data"] and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    lines = []

    # Agent health
    lines.append("# HELP hf_agent_up 1 if agent is healthy, 0 if down")
    lines.append("# TYPE hf_agent_up gauge")
    agent_rows = await db.fetch(
        "SELECT DISTINCT ON (agent) agent, status FROM agent_health ORDER BY agent, time DESC"
    )
    for row in agent_rows:
        val = 1.0 if row["status"] == "healthy" else 0.0
        lines.append(f'hf_agent_up{{agent="{row["agent"]}"}} {val}')

    # Portfolio
    lines.append("# HELP hf_portfolio_value_usd Current portfolio total value in USD")
    lines.append("# TYPE hf_portfolio_value_usd gauge")
    lines.append("# HELP hf_cash_usd Current cash balance in USD")
    lines.append("# TYPE hf_cash_usd gauge")
    lines.append("# HELP hf_open_positions_count Number of open positions")
    lines.append("# TYPE hf_open_positions_count gauge")
    lines.append("# HELP hf_portfolio_drawdown_pct Current drawdown from peak as percentage")
    lines.append("# TYPE hf_portfolio_drawdown_pct gauge")

    state = await db.fetchrow(
        "SELECT total_value, cash, open_positions, peak_value FROM portfolio_state ORDER BY time DESC LIMIT 1"
    )
    if state:
        total = float(state["total_value"])
        cash = float(state["cash"])
        open_pos = int(state["open_positions"])
        peak = float(state["peak_value"])
        drawdown = (peak - total) / peak * 100 if peak > 0 else 0.0
        lines.append(f"hf_portfolio_value_usd {total}")
        lines.append(f"hf_cash_usd {cash}")
        lines.append(f"hf_open_positions_count {open_pos}")
        lines.append(f"hf_portfolio_drawdown_pct {drawdown:.4f}")
    else:
        lines += ["hf_portfolio_value_usd 0", "hf_cash_usd 0",
                  "hf_open_positions_count 0", "hf_portfolio_drawdown_pct 0"]

    # Trades
    lines.append("# HELP hf_trades_total Total trades by status")
    lines.append("# TYPE hf_trades_total counter")
    trade_rows = await db.fetch("SELECT status, count(*) as cnt FROM trades GROUP BY status")
    for row in trade_rows:
        lines.append(f'hf_trades_total{{status="{row["status"]}"}} {row["cnt"]}')

    # Signals
    lines.append("# HELP hf_signals_total Total signals emitted per agent")
    lines.append("# TYPE hf_signals_total counter")
    signal_rows = await db.fetch("SELECT agent, count(*) as cnt FROM signals GROUP BY agent")
    for row in signal_rows:
        lines.append(f'hf_signals_total{{agent="{row["agent"]}"}} {row["cnt"]}')

    # Pending trades
    lines.append("# HELP hf_pending_trades_count Current pending trade queue depth")
    lines.append("# TYPE hf_pending_trades_count gauge")
    pending = await db.fetch("SELECT count(*) as cnt FROM trades WHERE status = 'pending'")
    lines.append(f"hf_pending_trades_count {pending[0]['cnt'] if pending else 0}")

    output = "\n".join(lines) + "\n"
    _cache["data"] = output
    _cache["ts"] = now
    return output


def _clear_cache():
    _cache["data"] = None
    _cache["ts"] = 0.0


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(db: Database = Depends(get_db)):
    _clear_cache()  # always fresh in tests; in prod TTL handles caching
    return await _collect(db)
