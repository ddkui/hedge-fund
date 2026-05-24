# Phase 4b — Portfolio, Risk, Execution, CIO & Ops Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the 6 agents that convert quant + AI signals into actual trades: RiskChecker (pre-trade validation), RiskAgent (running monitor), PortfolioManagerAgent (Kelly sizing + CIO dialogue), ExecutionAgent (paper/live fill), CIOAgent (LLM review + Redis directives), and OpsAgent (heartbeat monitoring + Gmail alerts).

**Architecture:** `PortfolioManagerAgent` calls `RiskChecker.validate()` synchronously before writing any trade. `ExecutionAgent` polls `trades WHERE status='pending'` every 5s and fills them (paper or live via Alpaca/Binance). `CIOAgent` publishes Redis directives (`cio:directive:{symbol}`) once per hour; PM re-analyzes independently on `request_close`. `OpsAgent` subscribes to `ops.heartbeat` continuously and emails on `down`. All agents use the existing `BaseAgent` poll pattern.

**Tech Stack:** asyncpg, redis-py async, alpaca-py, python-binance, smtplib (stdlib), structlog, numpy/pandas (already installed), shared `RedisBus.set/get`, `BaseAgent`, `AnalysisAgent`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `agents/risk/__init__.py` | Create | Package marker |
| `agents/risk/checker.py` | Create | `RiskChecker` — sync pre-trade validation class |
| `agents/risk/agent.py` | Create | `RiskAgent` — running monitor with force-close path |
| `agents/risk/main.py` | Create | Entry point |
| `agents/portfolio_mgr/__init__.py` | Create | Package marker |
| `agents/portfolio_mgr/agent.py` | Create | `PortfolioManagerAgent` — Kelly sizing, CIO handling, PM re-analysis |
| `agents/portfolio_mgr/main.py` | Create | Entry point |
| `agents/execution/__init__.py` | Create | Package marker |
| `agents/execution/agent.py` | Create | `ExecutionAgent` — 5s poll, paper/live modes |
| `agents/execution/main.py` | Create | Entry point |
| `agents/cio/__init__.py` | Create | Package marker |
| `agents/cio/agent.py` | Create | `CIOAgent` — LLM review, Redis directives, daily brief |
| `agents/cio/main.py` | Create | Entry point |
| `agents/ops/__init__.py` | Create | Package marker |
| `agents/ops/agent.py` | Create | `OpsAgent` — heartbeat subscription, Gmail alerts |
| `agents/ops/main.py` | Create | Entry point |
| `tests/agents/risk/__init__.py` | Create | Package marker |
| `tests/agents/risk/test_checker.py` | Create | 5 tests for RiskChecker |
| `tests/agents/risk/test_agent.py` | Create | 3 tests for RiskAgent |
| `tests/agents/portfolio_mgr/__init__.py` | Create | Package marker |
| `tests/agents/portfolio_mgr/test_agent.py` | Create | 5 tests for PortfolioManagerAgent |
| `tests/agents/execution/__init__.py` | Create | Package marker |
| `tests/agents/execution/test_agent.py` | Create | 4 tests for ExecutionAgent |
| `tests/agents/cio/__init__.py` | Create | Package marker |
| `tests/agents/cio/test_agent.py` | Create | 3 tests for CIOAgent |
| `tests/agents/ops/__init__.py` | Create | Package marker |
| `tests/agents/ops/test_agent.py` | Create | 3 tests for OpsAgent |
| `scripts/start_all.py` | Modify | Uncomment all Phase 4b agents |

---

## Task 6: RiskChecker

**Files:**
- Create: `agents/risk/__init__.py`
- Create: `agents/risk/checker.py`
- Create: `tests/agents/risk/__init__.py`
- Create: `tests/agents/risk/test_checker.py`

- [ ] **Step 1: Write failing tests**

Create `agents/risk/__init__.py` and `tests/agents/risk/__init__.py` (both empty).

Create `tests/agents/risk/test_checker.py`:

```python
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock
from agents.risk.checker import RiskChecker


def make_checker(
    portfolio_value=100_000.0,
    peak_value=100_000.0,
    open_positions=2,
    max_position_pct=0.10,
    max_positions=10,
    max_drawdown_pct=0.20,
    var_limit_pct=0.05,
    max_correlated=3,
):
    settings = MagicMock()
    settings.risk_max_position_pct = max_position_pct
    settings.risk_max_positions = max_positions
    settings.risk_max_drawdown_pct = max_drawdown_pct
    settings.risk_var_limit_pct = var_limit_pct
    settings.risk_max_correlated = max_correlated
    return RiskChecker(settings=settings)


@pytest.mark.asyncio
async def test_checker_approves_valid_trade():
    checker = make_checker()
    db = AsyncMock()
    # No open positions; simple price series for var
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=5.0,
        price=150.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is True
    assert reason == ""


@pytest.mark.asyncio
async def test_checker_rejects_oversized_position():
    checker = make_checker(max_position_pct=0.10)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=100.0,     # 100 * 200 = 20_000 = 20% of 100k
        price=200.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "position_size" in reason


@pytest.mark.asyncio
async def test_checker_rejects_too_many_positions():
    checker = make_checker(max_positions=3)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=100.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=3,     # already at max
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "open_positions" in reason


@pytest.mark.asyncio
async def test_checker_rejects_drawdown_breach():
    checker = make_checker(max_drawdown_pct=0.20)
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=100.0,
        portfolio_value=75_000.0,   # 25% drawdown from 100k peak
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=[],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "drawdown" in reason


@pytest.mark.asyncio
async def test_checker_rejects_correlated_positions():
    checker = make_checker(max_correlated=2)
    db = AsyncMock()
    # Return price series for 2 existing symbols + proposed — all highly correlated
    prices_up = [{"symbol": s, "close": float(100 + i)} for i in range(30) for s in ["MSFT", "GOOGL"]]
    # proposed AAPL is also rising — all three corr > 0.7
    db.fetch = AsyncMock(return_value=prices_up + [{"symbol": "AAPL", "close": float(100 + i)} for i in range(30)])
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)

    ok, reason = await checker.validate(
        symbol="AAPL",
        direction="long",
        quantity=1.0,
        price=130.0,
        portfolio_value=100_000.0,
        peak_value=100_000.0,
        open_position_count=2,
        open_symbols=["MSFT", "GOOGL"],
        db=db,
        bus=bus,
    )
    assert ok is False
    assert "correlation" in reason
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/agents/risk/test_checker.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.risk'`

- [ ] **Step 3: Create `agents/risk/checker.py`**

```python
import numpy as np
import pandas as pd
from typing import Any


class RiskChecker:
    """Synchronous pre-trade risk validation. Imported by PortfolioManagerAgent."""

    def __init__(self, settings: Any):
        self.settings = settings

    async def validate(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        portfolio_value: float,
        peak_value: float,
        open_position_count: int,
        open_symbols: list[str],
        db: Any,
        bus: Any,
    ) -> tuple[bool, str]:
        position_value = quantity * price

        # Position size check
        if portfolio_value > 0 and position_value / portfolio_value > self.settings.risk_max_position_pct:
            return False, f"position_size: {position_value:.0f} exceeds {self.settings.risk_max_position_pct*100:.0f}% of {portfolio_value:.0f}"

        # Open positions count check
        if open_position_count >= self.settings.risk_max_positions:
            return False, f"open_positions: already at max {self.settings.risk_max_positions}"

        # Drawdown check
        if peak_value > 0:
            drawdown = (peak_value - portfolio_value) / peak_value
            if drawdown >= self.settings.risk_max_drawdown_pct:
                return False, f"drawdown: {drawdown*100:.1f}% exceeds max {self.settings.risk_max_drawdown_pct*100:.0f}%"

        # VaR check (cached in Redis for 5 min)
        var_ok, var_msg = await self._check_var(portfolio_value, open_symbols, db, bus)
        if not var_ok:
            return False, var_msg

        # Correlation check
        if open_symbols:
            corr_ok, corr_msg = await self._check_correlation(symbol, open_symbols, db)
            if not corr_ok:
                return False, corr_msg

        return True, ""

    async def _check_var(
        self, portfolio_value: float, open_symbols: list[str], db: Any, bus: Any
    ) -> tuple[bool, str]:
        if not open_symbols:
            return True, ""

        cached = await bus.get("risk:var_cache")
        if cached is not None:
            var_pct = float(cached)
        else:
            rows = await db.fetch(
                """
                SELECT symbol, close FROM prices
                WHERE symbol = ANY($1) AND time > NOW() - INTERVAL '30 days'
                ORDER BY symbol, time ASC
                """,
                open_symbols,
            )
            if not rows:
                return True, ""

            df = pd.DataFrame(rows)
            pivot = df.pivot_table(index=df.groupby("symbol").cumcount(), columns="symbol", values="close")
            returns = pivot.pct_change().dropna()
            if returns.empty:
                return True, ""

            portfolio_returns = returns.mean(axis=1)
            var_pct = float(-np.percentile(portfolio_returns, 5))
            await bus.set("risk:var_cache", var_pct, ex=300)

        var_abs = var_pct * portfolio_value
        limit_abs = self.settings.risk_var_limit_pct * portfolio_value
        if var_abs > limit_abs:
            return False, f"var: daily VaR {var_abs:.0f} exceeds limit {limit_abs:.0f}"
        return True, ""

    async def _check_correlation(
        self, symbol: str, open_symbols: list[str], db: Any
    ) -> tuple[bool, str]:
        all_symbols = open_symbols + [symbol]
        rows = await db.fetch(
            """
            SELECT symbol, close FROM prices
            WHERE symbol = ANY($1) AND time > NOW() - INTERVAL '20 days'
            ORDER BY symbol, time ASC
            """,
            all_symbols,
        )
        if not rows:
            return True, ""

        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index=df.groupby("symbol").cumcount(), columns="symbol", values="close")
        returns = pivot.pct_change().dropna()

        if symbol not in returns.columns:
            return True, ""

        corr_count = 0
        for sym in open_symbols:
            if sym not in returns.columns:
                continue
            pair_corr = returns[symbol].corr(returns[sym])
            if abs(pair_corr) > 0.7:
                corr_count += 1

        if corr_count >= self.settings.risk_max_correlated:
            return False, f"correlation: {symbol} correlated (>0.7) with {corr_count} existing positions (max {self.settings.risk_max_correlated})"
        return True, ""
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/risk/test_checker.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add agents/risk/ tests/agents/risk/
git commit -m "feat: RiskChecker with position-size, drawdown, VaR, and correlation checks"
```

---

## Task 7: RiskAgent

**Files:**
- Create: `agents/risk/agent.py`
- Create: `agents/risk/main.py`
- Create: `tests/agents/risk/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `tests/agents/risk/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.risk.agent import RiskAgent


def make_agent():
    settings = MagicMock()
    settings.risk_max_position_pct = 0.10
    settings.risk_max_positions = 10
    settings.risk_max_drawdown_pct = 0.20
    settings.risk_var_limit_pct = 0.05
    settings.risk_max_correlated = 3
    with patch("agents.risk.agent.settings", settings):
        agent = RiskAgent(
            name="risk",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=120,
        )
    agent._settings = settings
    return agent


OPEN_POSITIONS = [
    {"symbol": "AAPL", "quantity": 10.0, "direction": "long", "entry_price": 150.0},
]

PORTFOLIO_ROW = {"cash": 90_000.0, "total_value": 95_000.0, "peak_value": 100_000.0, "open_positions": 1}


@pytest.mark.asyncio
async def test_risk_agent_no_breach_no_trade():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],  # current prices
        [],  # var fetch — empty → skip var
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    # No drawdown breach (5% < 20%), no trade inserted
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 0


@pytest.mark.asyncio
async def test_risk_agent_force_closes_on_drawdown():
    agent = make_agent()
    # 25% drawdown → force close
    agent.db.fetchrow = AsyncMock(return_value={
        "cash": 75_000.0, "total_value": 75_000.0, "peak_value": 100_000.0, "open_positions": 1
    })
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],
        [],
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    # Should insert a close trade for the largest loser
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1


@pytest.mark.asyncio
async def test_risk_agent_logs_breach_to_risk_events():
    agent = make_agent()
    agent.db.fetchrow = AsyncMock(return_value={
        "cash": 75_000.0, "total_value": 75_000.0, "peak_value": 100_000.0, "open_positions": 1
    })
    agent.db.fetch = AsyncMock(side_effect=[
        OPEN_POSITIONS,
        [{"symbol": "AAPL", "close": 150.0}],
        [],
    ])
    agent.bus.get = AsyncMock(return_value=None)
    await agent.run_once()
    risk_event_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO risk_events" in str(c)]
    assert len(risk_event_calls) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/risk/test_agent.py -v
```

Expected: FAIL with `ImportError` (no `agents.risk.agent`)

- [ ] **Step 3: Create `agents/risk/agent.py`**

```python
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings
from agents.risk.checker import RiskChecker


class RiskAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._checker = RiskChecker(settings=settings)

    async def run_once(self):
        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        if not state:
            return

        portfolio_value = float(state["total_value"])
        peak_value = float(state["peak_value"])
        open_count = int(state["open_positions"])

        positions = await self.db.fetch(
            "SELECT symbol, quantity, direction, entry_price FROM positions WHERE status = 'open'"
        )
        if not positions:
            return

        open_symbols = [p["symbol"] for p in positions]
        price_rows = await self.db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            open_symbols,
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        # Drawdown check
        if peak_value > 0:
            drawdown = (peak_value - portfolio_value) / peak_value
            if drawdown >= settings.risk_max_drawdown_pct:
                await self._log_event("risk", None, "drawdown", f"{drawdown*100:.1f}% exceeds {settings.risk_max_drawdown_pct*100:.0f}%", "position_force_closed")
                await self._force_close_largest_loser(positions, prices)

    async def _force_close_largest_loser(self, positions: list, prices: dict):
        worst = None
        worst_pnl = 0.0
        for pos in positions:
            sym = pos["symbol"]
            price = prices.get(sym)
            if price is None:
                continue
            pnl = (price - float(pos["entry_price"])) * float(pos["quantity"])
            if pos["direction"] == "short":
                pnl = -pnl
            if worst is None or pnl < worst_pnl:
                worst = pos
                worst_pnl = pnl

        if worst is None:
            return

        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO trades (time, symbol, direction, quantity, status, paper, pm_reasoning, confidence)
            VALUES ($1, $2, 'close', $3, 'pending', $4, $5, $6)
            """,
            now,
            worst["symbol"],
            float(worst["quantity"]),
            True,
            "RiskAgent force-close: drawdown limit breached",
            0.0,
        )
        self.logger.warning("force_close_issued", symbol=worst["symbol"], pnl=worst_pnl)

    async def _log_event(self, agent: str, symbol, limit_type: str, details: str, action_taken: str):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,$2,$3,$4,$5,$6)",
            now, agent, symbol, limit_type, details, action_taken,
        )
```

Create `agents/risk/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.risk.agent import RiskAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = RiskAgent(name="risk", bus=bus, db=db, router=router, interval_seconds=120)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/risk/test_agent.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add agents/risk/agent.py agents/risk/main.py tests/agents/risk/test_agent.py
git commit -m "feat: RiskAgent with drawdown monitor and force-close path"
```

---

## Task 8: PortfolioManagerAgent

**Files:**
- Create: `agents/portfolio_mgr/__init__.py`
- Create: `agents/portfolio_mgr/agent.py`
- Create: `agents/portfolio_mgr/main.py`
- Create: `tests/agents/portfolio_mgr/__init__.py`
- Create: `tests/agents/portfolio_mgr/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `agents/portfolio_mgr/__init__.py` and `tests/agents/portfolio_mgr/__init__.py` (both empty).

Create `tests/agents/portfolio_mgr/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.portfolio_mgr.agent import PortfolioManagerAgent

AGG_SIGNAL = {"agent": "aggregator", "symbol": "AAPL", "signal_type": "consensus_bullish", "confidence": 80.0, "time": None}
QUANT_SIGNAL = {"agent": "quant_supervisor", "symbol": "AAPL", "signal_type": "quant_bullish", "confidence": 70.0, "time": None}
PORTFOLIO_ROW = {"cash": 100_000.0, "total_value": 100_000.0, "peak_value": 100_000.0, "open_positions": 0}
PRICE_ROW = {"close": 150.0}


def make_agent():
    settings = MagicMock()
    settings.kelly_multiplier = 0.25
    settings.risk_max_position_pct = 0.10
    settings.risk_max_positions = 10
    settings.risk_max_drawdown_pct = 0.20
    settings.risk_var_limit_pct = 0.05
    settings.risk_max_correlated = 3
    settings.paper_trading = True
    with patch("agents.portfolio_mgr.agent.settings", settings):
        agent = PortfolioManagerAgent(
            name="portfolio_mgr",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=120,
        )
    agent._settings = settings
    return agent


@pytest.mark.asyncio
async def test_pm_opens_long_on_bullish_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],          # aggregator signals
        [QUANT_SIGNAL],        # quant_supervisor signals
        [],                    # existing positions
        [PRICE_ROW],           # current price fetch
        [],                    # var cache miss fetch (correlation — no open symbols)
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)  # no CIO directive

    # Mock RiskChecker to approve
    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(True, ""))
        await agent.run_once()

    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    assert "long" in args
    assert "pending" in args


@pytest.mark.asyncio
async def test_pm_skips_when_position_already_open():
    agent = make_agent()
    open_pos = {"symbol": "AAPL", "direction": "long", "quantity": 5.0, "status": "open"}
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [open_pos],     # already long AAPL
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    await agent.run_once()
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 0


@pytest.mark.asyncio
async def test_pm_applies_cio_low_conviction():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [],
        [PRICE_ROW],
        [],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    # CIO says low_conviction with 0.5 multiplier
    agent.bus.get = AsyncMock(return_value={"action": "low_conviction", "confidence_multiplier": 0.5, "reason": "uncertain"})

    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(True, ""))
        await agent.run_once()

    # Should still open but with lower confidence
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    confidence = args[7]   # confidence is 8th positional arg
    assert confidence < 80.0  # reduced from 76 (0.6*80 + 0.4*70) * 0.5


@pytest.mark.asyncio
async def test_pm_risk_rejection_writes_risk_event():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [AGG_SIGNAL],
        [QUANT_SIGNAL],
        [],
        [PRICE_ROW],
        [],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    with patch("agents.portfolio_mgr.agent.RiskChecker") as MockChecker:
        MockChecker.return_value.validate = AsyncMock(return_value=(False, "drawdown: 25% exceeds max 20%"))
        await agent.run_once()

    risk_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO risk_events" in str(c)]
    assert len(risk_calls) == 1


@pytest.mark.asyncio
async def test_pm_closes_on_neutral_signal():
    agent = make_agent()
    neutral_signal = {**AGG_SIGNAL, "signal_type": "consensus_neutral"}
    open_pos = {"symbol": "AAPL", "direction": "long", "quantity": 5.0, "status": "open"}
    agent.db.fetch = AsyncMock(side_effect=[
        [neutral_signal],
        [],        # no quant signal
        [open_pos],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.bus.get = AsyncMock(return_value=None)

    await agent.run_once()
    trade_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO trades" in str(c)]
    assert len(trade_calls) == 1
    args = trade_calls[0][0]
    assert "close" in args
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/portfolio_mgr/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.portfolio_mgr'`

- [ ] **Step 3: Create `agents/portfolio_mgr/agent.py`**

```python
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings
from agents.risk.checker import RiskChecker


def _direction(signal_type: str) -> str:
    st = signal_type.lower()
    if "bullish" in st:
        return "bullish"
    if "bearish" in st:
        return "bearish"
    return "neutral"


class PortfolioManagerAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._checker = RiskChecker(settings=settings)

    async def run_once(self):
        agg_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE agent = 'aggregator' AND time > NOW() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """
        )
        quant_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE agent = 'quant_supervisor' AND time > NOW() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """
        )

        quant_by_symbol = {s["symbol"]: s for s in quant_signals}

        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        portfolio_value = float(state["total_value"]) if state else settings.initial_capital
        peak_value = float(state["peak_value"]) if state else settings.initial_capital
        open_count = int(state["open_positions"]) if state else 0

        open_positions = await self.db.fetch(
            "SELECT symbol, direction, quantity FROM positions WHERE status = 'open'"
        )
        open_by_symbol = {p["symbol"]: p for p in open_positions}
        open_symbols = list(open_by_symbol.keys())

        seen_symbols: set[str] = set()
        for sig in agg_signals:
            symbol = sig["symbol"]
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            agg_conf = float(sig["confidence"])
            agg_dir = _direction(sig["signal_type"])

            quant_sig = quant_by_symbol.get(symbol)
            quant_conf = float(quant_sig["confidence"]) if quant_sig else 0.0

            combined_confidence = agg_conf * 0.60 + quant_conf * 0.40

            # CIO directive check
            directive = await self.bus.get(f"cio:directive:{symbol}")
            if directive:
                action = directive.get("action", "none")
                if action == "low_conviction":
                    combined_confidence *= float(directive.get("confidence_multiplier", 1.0))
                elif action == "avoid_open" and agg_dir != "neutral":
                    if combined_confidence <= 85.0:
                        continue
                    await self._store_cio_override(symbol, "PM overrides avoid_open: confidence > 85", combined_confidence)
                elif action == "request_close":
                    await self._handle_request_close(symbol, open_by_symbol, portfolio_value, peak_value, open_count, open_symbols)
                    continue

            existing = open_by_symbol.get(symbol)

            if agg_dir == "neutral" and existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "consensus_neutral: closing position", combined_confidence)
                continue

            if agg_dir == "neutral":
                continue

            if existing:
                continue  # no pyramiding

            price_rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                symbol,
            )
            if not price_rows:
                continue
            current_price = float(price_rows[0]["close"])

            kelly_fraction = (combined_confidence / 100.0) * settings.kelly_multiplier
            position_value = portfolio_value * kelly_fraction
            position_value = max(portfolio_value * 0.005, min(position_value, portfolio_value * settings.risk_max_position_pct))
            quantity = position_value / current_price if current_price > 0 else 0.0

            if quantity <= 0:
                continue

            direction = "long" if agg_dir == "bullish" else "short"

            # Crypto is long-only
            if symbol.upper().endswith("USDT") and direction == "short":
                continue

            ok, reason = await self._checker.validate(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                price=current_price,
                portfolio_value=portfolio_value,
                peak_value=peak_value,
                open_position_count=open_count,
                open_symbols=open_symbols,
                db=self.db,
                bus=self.bus,
            )

            if not ok:
                await self._log_risk_event(symbol, "trade_rejected", reason)
                continue

            await self._write_trade(symbol, direction, quantity, current_price, portfolio_value, f"agg_dir={agg_dir}, conf={combined_confidence:.1f}", combined_confidence)

    async def _handle_request_close(self, symbol: str, open_by_symbol: dict, portfolio_value: float, peak_value: float, open_count: int, open_symbols: list):
        fresh_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE symbol = $1 AND agent IN ('aggregator', 'quant_supervisor')
              AND time > NOW() - INTERVAL '5 minutes'
            ORDER BY time DESC
            """,
            symbol,
        )
        if not fresh_signals:
            # No fresh data — agree with CIO
            existing = open_by_symbol.get(symbol)
            if existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "CIO request confirmed: no fresh signals", 0.0)
            return

        agg = next((s for s in fresh_signals if s["agent"] == "aggregator"), None)
        conf = float(agg["confidence"]) if agg else 0.0
        direction = _direction(agg["signal_type"]) if agg else "neutral"

        existing = open_by_symbol.get(symbol)
        if conf > 70 and direction in ("bullish", "bearish"):
            # PM disagrees — override
            await self._store_cio_override(symbol, f"PM disagrees with request_close: fresh conf={conf:.1f}", conf)
        elif 40 <= conf <= 70:
            # Mixed — log as low_conviction but don't close
            await self.store_signal(
                symbol=symbol,
                signal_type="low_conviction",
                confidence=conf * 0.5,
                reasoning="CIO request_close: mixed signals, applying 0.5 multiplier",
            )
        else:
            # Weak/bearish — agree and close
            if existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "CIO request confirmed", conf)

    async def _store_cio_override(self, symbol: str, reasoning: str, confidence: float):
        await self.store_signal(
            symbol=symbol,
            signal_type="cio_override",
            confidence=confidence,
            reasoning=reasoning,
            metadata={"cio_override": True},
        )

    async def _write_trade(self, symbol: str, direction: str, quantity: float, price: float, portfolio_value: float, reasoning: str, confidence: float):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO trades (time, symbol, direction, quantity, status, paper, pm_reasoning, confidence)
            VALUES ($1, $2, $3, $4, 'pending', $5, $6, $7)
            """,
            now, symbol, direction, quantity, settings.paper_trading, reasoning, confidence,
        )
        self.logger.info("trade_written", symbol=symbol, direction=direction, quantity=quantity)

    async def _log_risk_event(self, symbol: str, action_taken: str, reason: str):
        now = datetime.now(timezone.utc)
        limit_type = reason.split(":")[0].strip() if ":" in reason else "unknown"
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,$2,$3,$4,$5,$6)",
            now, self.name, symbol, limit_type, reason, action_taken,
        )
```

Create `agents/portfolio_mgr/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.portfolio_mgr.agent import PortfolioManagerAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = PortfolioManagerAgent(name="portfolio_mgr", bus=bus, db=db, router=router, interval_seconds=120)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/portfolio_mgr/test_agent.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```
git add agents/portfolio_mgr/ tests/agents/portfolio_mgr/
git commit -m "feat: PortfolioManagerAgent with Kelly sizing, CIO directive handling, and PM re-analysis"
```

---

## Task 9: ExecutionAgent

**Files:**
- Create: `agents/execution/__init__.py`
- Create: `agents/execution/agent.py`
- Create: `agents/execution/main.py`
- Create: `tests/agents/execution/__init__.py`
- Create: `tests/agents/execution/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `agents/execution/__init__.py` and `tests/agents/execution/__init__.py` (both empty).

Create `tests/agents/execution/test_agent.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.execution.agent import ExecutionAgent

PENDING_TRADE = {
    "id": 1,
    "symbol": "AAPL",
    "direction": "long",
    "quantity": 5.0,
    "paper": True,
    "status": "pending",
}
PRICE_ROW = {"close": 151.0}
PORTFOLIO_ROW = {"cash": 100_000.0, "total_value": 100_000.0, "peak_value": 100_000.0, "open_positions": 0}


def make_agent(paper=True):
    settings = MagicMock()
    settings.paper_trading = paper
    settings.initial_capital = 100_000.0
    with patch("agents.execution.agent.settings", settings):
        agent = ExecutionAgent(
            name="execution",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=5,
        )
    agent._settings = settings
    return agent


@pytest.mark.asyncio
async def test_execution_fills_paper_trade():
    agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(side_effect=[
        [PENDING_TRADE],          # pending trades
        [PRICE_ROW],              # latest price
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    await agent.run_once()

    update_calls = [c for c in agent.db.execute.call_args_list if "UPDATE trades" in str(c)]
    assert len(update_calls) == 1
    args = update_calls[0][0]
    assert "executed" in args
    assert 151.0 in args


@pytest.mark.asyncio
async def test_execution_updates_portfolio_state_on_fill():
    agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(side_effect=[
        [PENDING_TRADE],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    await agent.run_once()

    state_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO portfolio_state" in str(c)]
    assert len(state_calls) == 1


@pytest.mark.asyncio
async def test_execution_skips_when_no_pending():
    agent = make_agent(paper=True)
    agent.db.fetch = AsyncMock(return_value=[])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)

    await agent.run_once()
    agent.db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_execution_closes_position_on_close_trade():
    agent = make_agent(paper=True)
    close_trade = {**PENDING_TRADE, "direction": "close"}
    agent.db.fetch = AsyncMock(side_effect=[
        [close_trade],
        [PRICE_ROW],
    ])
    agent.db.fetchrow = AsyncMock(return_value=PORTFOLIO_ROW)
    agent.db.execute = AsyncMock()

    await agent.run_once()

    position_calls = [c for c in agent.db.execute.call_args_list if "UPDATE positions" in str(c)]
    assert len(position_calls) == 1
    args = position_calls[0][0]
    assert "closed" in args
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/execution/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.execution'`

- [ ] **Step 3: Create `agents/execution/agent.py`**

```python
import asyncio
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.config import settings


class ExecutionAgent(BaseAgent):
    async def run_once(self):
        pending = await self.db.fetch(
            "SELECT id, symbol, direction, quantity, paper FROM trades WHERE status = 'pending' ORDER BY time ASC"
        )
        if not pending:
            return

        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        cash = float(state["cash"]) if state else settings.initial_capital
        total_value = float(state["total_value"]) if state else settings.initial_capital
        peak_value = float(state["peak_value"]) if state else settings.initial_capital
        open_positions = int(state["open_positions"]) if state else 0

        for trade in pending:
            fill_price = await self._get_fill_price(trade)
            if fill_price is None:
                continue
            cash, total_value, peak_value, open_positions = await self._apply_fill(
                trade, fill_price, cash, total_value, peak_value, open_positions
            )

    async def _get_fill_price(self, trade: dict) -> float | None:
        if trade.get("paper", True) or settings.paper_trading:
            rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                trade["symbol"],
            )
            if not rows:
                return None
            return float(rows[0]["close"])

        # Live mode
        symbol = trade["symbol"]
        if symbol.upper().endswith("USDT"):
            return await self._binance_fill(trade)
        return await self._alpaca_fill(trade)

    async def _alpaca_fill(self, trade: dict) -> float | None:
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.requests import MarketOrderRequest
            from alpaca.trading.enums import OrderSide, TimeInForce

            client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=False)
            side = OrderSide.BUY if trade["direction"] == "long" else OrderSide.SELL
            req = MarketOrderRequest(symbol=trade["symbol"], qty=trade["quantity"], side=side, time_in_force=TimeInForce.DAY)
            order = client.submit_order(req)
            return float(order.filled_avg_price) if order.filled_avg_price else None
        except Exception as exc:
            self.logger.error("alpaca_fill_failed", symbol=trade["symbol"], error=str(exc))
            await asyncio.sleep(2)
            try:
                client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=False)
                side = OrderSide.BUY if trade["direction"] == "long" else OrderSide.SELL
                req = MarketOrderRequest(symbol=trade["symbol"], qty=trade["quantity"], side=side, time_in_force=TimeInForce.DAY)
                order = client.submit_order(req)
                return float(order.filled_avg_price) if order.filled_avg_price else None
            except Exception as exc2:
                await self._fail_trade(trade["id"], str(exc2))
                return None

    async def _binance_fill(self, trade: dict) -> float | None:
        try:
            from binance.client import Client
            client = Client(settings.binance_api_key, settings.binance_secret_key)
            side = "BUY" if trade["direction"] == "long" else "SELL"
            order = client.create_order(symbol=trade["symbol"], side=side, type="MARKET", quantity=trade["quantity"])
            fills = order.get("fills", [])
            if fills:
                return float(fills[0]["price"])
            return None
        except Exception as exc:
            self.logger.error("binance_fill_failed", symbol=trade["symbol"], error=str(exc))
            await asyncio.sleep(2)
            try:
                client = Client(settings.binance_api_key, settings.binance_secret_key)
                side = "BUY" if trade["direction"] == "long" else "SELL"
                order = client.create_order(symbol=trade["symbol"], side=side, type="MARKET", quantity=trade["quantity"])
                fills = order.get("fills", [])
                return float(fills[0]["price"]) if fills else None
            except Exception as exc2:
                await self._fail_trade(trade["id"], str(exc2))
                return None

    async def _apply_fill(self, trade: dict, fill_price: float, cash: float, total_value: float, peak_value: float, open_positions: int) -> tuple[float, float, float, int]:
        now = datetime.now(timezone.utc)
        symbol = trade["symbol"]
        quantity = float(trade["quantity"])
        direction = trade["direction"]
        trade_value = quantity * fill_price

        await self.db.execute(
            "UPDATE trades SET status = 'executed', price = $1 WHERE id = $2",
            fill_price, trade["id"],
        )

        if direction == "close":
            await self.db.execute(
                "UPDATE positions SET exit_price = $1, exit_time = $2, status = 'closed' WHERE symbol = $3 AND status = 'open'",
                fill_price, now, symbol,
            )
            cash += trade_value
            open_positions = max(0, open_positions - 1)
        else:
            await self.db.execute(
                "INSERT INTO positions (time, symbol, direction, quantity, entry_price, status) VALUES ($1, $2, $3, $4, $5, 'open')",
                now, symbol, direction, quantity, fill_price,
            )
            cash -= trade_value
            open_positions += 1

        total_value = cash + (open_positions * fill_price * quantity)
        peak_value = max(peak_value, total_value)

        await self.db.execute(
            "INSERT INTO portfolio_state (time, cash, total_value, peak_value, open_positions) VALUES ($1, $2, $3, $4, $5)",
            now, cash, total_value, peak_value, open_positions,
        )
        self.logger.info("trade_executed", symbol=symbol, direction=direction, fill_price=fill_price, quantity=quantity)
        return cash, total_value, peak_value, open_positions

    async def _fail_trade(self, trade_id: int, error: str):
        now = datetime.now(timezone.utc)
        await self.db.execute("UPDATE trades SET status = 'failed' WHERE id = $1", trade_id)
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,'execution',NULL,'broker_error',$2,'trade_failed')",
            now, error,
        )
```

Create `agents/execution/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.execution.agent import ExecutionAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = ExecutionAgent(name="execution", bus=bus, db=db, router=router, interval_seconds=5)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/execution/test_agent.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```
git add agents/execution/ tests/agents/execution/
git commit -m "feat: ExecutionAgent with paper fill, position/portfolio state updates"
```

---

## Task 10: CIOAgent

**Files:**
- Create: `agents/cio/__init__.py`
- Create: `agents/cio/agent.py`
- Create: `agents/cio/main.py`
- Create: `tests/agents/cio/__init__.py`
- Create: `tests/agents/cio/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `agents/cio/__init__.py` and `tests/agents/cio/__init__.py` (both empty).

Create `tests/agents/cio/test_agent.py`:

```python
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from agents.cio.agent import CIOAgent

OPEN_POSITIONS = [{"symbol": "AAPL", "direction": "long", "quantity": 10.0, "entry_price": 145.0, "status": "open"}]
PRICE_ROW = [{"symbol": "AAPL", "close": 150.0}]
CLOSED_TRADES = []
MACRO_SIGNAL = [{"signal_type": "expansion", "confidence": 70.0, "time": None}]
RISK_EVENTS = []
CIO_OVERRIDES = []

LLM_RESPONSE = json.dumps([
    {"symbol": "AAPL", "action": "low_conviction", "confidence_multiplier": 0.7, "reason": "earnings uncertainty"}
])


def make_agent():
    with patch("agents.cio.agent.settings"):
        agent = CIOAgent(
            name="cio",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=3600,
        )
    return agent


@pytest.mark.asyncio
async def test_cio_publishes_directive_to_redis():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],                # last 24h signals (all agents) - simplified
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value=LLM_RESPONSE)

    await agent.run_once()

    set_calls = [c for c in agent.bus.set.call_args_list]
    keys = [c[0][0] for c in set_calls]
    assert any("cio:directive:AAPL" in k for k in keys)


@pytest.mark.asyncio
async def test_cio_writes_daily_brief_signal():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value=LLM_RESPONSE)

    await agent.run_once()

    signal_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO signals" in str(c)]
    assert len(signal_calls) >= 1
    args = signal_calls[0][0]
    assert "daily_brief" in args


@pytest.mark.asyncio
async def test_cio_handles_malformed_llm_response():
    agent = make_agent()
    agent.db.fetch = AsyncMock(side_effect=[
        [],
        OPEN_POSITIONS,
        PRICE_ROW,
        CLOSED_TRADES,
        MACRO_SIGNAL,
        RISK_EVENTS,
        CIO_OVERRIDES,
    ])
    agent.router.complete = AsyncMock(return_value="not valid json at all")

    await agent.run_once()

    # Should not crash; still writes daily brief with no directives
    signal_calls = [c for c in agent.db.execute.call_args_list if "INSERT INTO signals" in str(c)]
    assert len(signal_calls) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/cio/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.cio'`

- [ ] **Step 3: Create `agents/cio/agent.py`**

```python
import json
import re
from datetime import datetime, timezone
from agents.base import AnalysisAgent
from shared.config import settings

DIRECTIVE_TTL_SECONDS = 25 * 3600  # 25 hours


class CIOAgent(AnalysisAgent):
    async def run_once(self):
        now = datetime.now(timezone.utc)

        all_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, reasoning, time
            FROM signals
            WHERE time > NOW() - INTERVAL '24 hours'
            ORDER BY time DESC
            LIMIT 200
            """
        )
        open_positions = await self.db.fetch(
            "SELECT symbol, direction, quantity, entry_price FROM positions WHERE status = 'open'"
        )
        price_rows = await self.db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            [p["symbol"] for p in open_positions] or ["__none__"],
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        positions_with_pnl = []
        for pos in open_positions:
            price = prices.get(pos["symbol"], float(pos["entry_price"]))
            pnl = (price - float(pos["entry_price"])) * float(pos["quantity"])
            positions_with_pnl.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "quantity": float(pos["quantity"]),
                "entry_price": float(pos["entry_price"]),
                "current_price": price,
                "unrealized_pnl": round(pnl, 2),
            })

        closed_trades = await self.db.fetch(
            """
            SELECT symbol, direction, quantity, price, pm_reasoning, time
            FROM trades
            WHERE status = 'executed' AND time > NOW() - INTERVAL '7 days'
            ORDER BY time DESC
            LIMIT 50
            """
        )
        macro_signal = await self.db.fetch(
            "SELECT signal_type, confidence, time FROM signals WHERE agent = 'macro' ORDER BY time DESC LIMIT 1"
        )
        risk_events = await self.db.fetch(
            "SELECT limit_type, details, action_taken, time FROM risk_events WHERE time > NOW() - INTERVAL '24 hours'"
        )
        cio_overrides = await self.db.fetch(
            "SELECT symbol, reasoning, time FROM signals WHERE signal_type = 'cio_override' AND time > NOW() - INTERVAL '24 hours'"
        )

        macro_regime = macro_signal[0]["signal_type"] if macro_signal else "unknown"

        prompt = self._build_prompt(
            positions=positions_with_pnl,
            closed_trades=[dict(r) for r in closed_trades],
            macro_regime=macro_regime,
            risk_events=[dict(r) for r in risk_events],
            cio_overrides=[dict(r) for r in cio_overrides],
            recent_signals=[dict(r) for r in all_signals[:30]],
        )

        raw_response = await self.router.complete(
            prompt=prompt,
            model=settings.ollama_research_model,
            system="You are a Chief Investment Officer. Respond only with a valid JSON array of directives.",
        )

        directives = self._parse_directives(raw_response)

        for directive in directives:
            if directive.get("action", "none") == "none":
                continue
            symbol = directive.get("symbol")
            if not symbol:
                continue
            await self.bus.set(
                f"cio:directive:{symbol}",
                {
                    "action": directive["action"],
                    "reason": directive.get("reason", ""),
                    "confidence_multiplier": float(directive.get("confidence_multiplier", 1.0)),
                },
                ex=DIRECTIVE_TTL_SECONDS,
            )
            self.logger.info("cio_directive_set", symbol=symbol, action=directive["action"])

        pm_pushback_note = ""
        if cio_overrides:
            pm_pushback_note = f" PM overrode {len(cio_overrides)} CIO directive(s)."

        await self.store_signal(
            signal_type="daily_brief",
            confidence=100.0,
            reasoning=f"Regime={macro_regime}. {len(directives)} directives issued.{pm_pushback_note} Raw: {raw_response[:500]}",
            metadata={
                "positions": positions_with_pnl,
                "directives": directives,
                "regime": macro_regime,
                "risk_events_count": len(risk_events),
                "cio_overrides_count": len(cio_overrides),
            },
        )

    def _build_prompt(self, positions, closed_trades, macro_regime, risk_events, cio_overrides, recent_signals) -> str:
        return f"""You are reviewing the hedge fund portfolio. Current macro regime: {macro_regime}.

Open positions with unrealized P&L:
{json.dumps(positions, indent=2)}

Recent closed trades (last 7 days):
{json.dumps(closed_trades[:10], indent=2, default=str)}

Recent risk events (last 24h):
{json.dumps(risk_events, indent=2, default=str)}

PM pushbacks on prior CIO directives:
{json.dumps(cio_overrides, indent=2, default=str)}

Based on this, provide a JSON array of per-symbol directives. Each item:
{{
  "symbol": "TICKER",
  "action": "low_conviction" | "avoid_open" | "request_close" | "none",
  "confidence_multiplier": 0.0-1.0,
  "reason": "one sentence"
}}

Return ONLY the JSON array, nothing else."""

    def _parse_directives(self, raw: str) -> list[dict]:
        try:
            # Strip markdown code fences if present
            cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("cio_parse_failed", raw=raw[:200])
            return []
```

Create `agents/cio/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.cio.agent import CIOAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = CIOAgent(name="cio", bus=bus, db=db, router=router, interval_seconds=3600)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/cio/test_agent.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add agents/cio/ tests/agents/cio/
git commit -m "feat: CIOAgent with LLM review, Redis directives, and daily brief"
```

---

## Task 11: OpsAgent

**Files:**
- Create: `agents/ops/__init__.py`
- Create: `agents/ops/agent.py`
- Create: `agents/ops/main.py`
- Create: `tests/agents/ops/__init__.py`
- Create: `tests/agents/ops/test_agent.py`

- [ ] **Step 1: Write failing tests**

Create `agents/ops/__init__.py` and `tests/agents/ops/__init__.py` (both empty).

Create `tests/agents/ops/test_agent.py`:

```python
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from agents.ops.agent import OpsAgent

KNOWN_AGENTS = {
    "technical": 120,
    "sentiment": 300,
    "macro": 300,
}


def make_agent():
    with patch("agents.ops.agent.settings") as mock_settings:
        mock_settings.gmail_sender = "alerts@example.com"
        agent = OpsAgent(
            name="ops",
            bus=AsyncMock(),
            db=AsyncMock(),
            router=AsyncMock(),
            interval_seconds=60,
        )
    agent._known_agents = KNOWN_AGENTS.copy()
    return agent


@pytest.mark.asyncio
async def test_ops_marks_agent_healthy_on_heartbeat():
    agent = make_agent()
    now = datetime.now(timezone.utc)
    agent._last_seen["technical"] = now

    await agent._check_agents()

    healthy_calls = [c for c in agent.db.execute.call_args_list if "agent_health" in str(c)]
    assert len(healthy_calls) == 0  # healthy = only written on heartbeat receive, not check cycle


@pytest.mark.asyncio
async def test_ops_detects_degraded_agent():
    agent = make_agent()
    # technical has interval 120s; if last seen > 2*120 = 240s ago → degraded
    agent._last_seen["technical"] = datetime.now(timezone.utc) - timedelta(seconds=300)

    await agent._check_agents()

    degraded_calls = [c for c in agent.db.execute.call_args_list if "degraded" in str(c)]
    assert len(degraded_calls) >= 1


@pytest.mark.asyncio
async def test_ops_detects_down_agent():
    agent = make_agent()
    # technical has interval 120s; if last seen > 5*120 = 600s ago → down
    agent._last_seen["technical"] = datetime.now(timezone.utc) - timedelta(seconds=700)

    with patch("agents.ops.agent.smtplib") as mock_smtp:
        mock_smtp.SMTP_SSL.return_value.__enter__ = MagicMock(return_value=MagicMock())
        mock_smtp.SMTP_SSL.return_value.__exit__ = MagicMock(return_value=False)
        await agent._check_agents()

    down_calls = [c for c in agent.db.execute.call_args_list if "'down'" in str(c)]
    assert len(down_calls) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
.venv\Scripts\pytest tests/agents/ops/test_agent.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'agents.ops'`

- [ ] **Step 3: Create `agents/ops/agent.py`**

```python
import asyncio
import smtplib
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from shared.agent_base import BaseAgent
from shared.config import settings

KNOWN_AGENT_INTERVALS: dict[str, int] = {
    "ingest":          60,
    "technical":       120,
    "sentiment":       300,
    "macro":           300,
    "research":        600,
    "aggregator":      120,
    "momentum":        120,
    "mean_reversion":  120,
    "ml_quant":        120,
    "quant_supervisor":300,
    "portfolio_mgr":   120,
    "risk":            120,
    "execution":       5,
    "cio":             3600,
}


class OpsAgent(BaseAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_seen: dict[str, datetime] = {}
        self._known_agents: dict[str, int] = KNOWN_AGENT_INTERVALS.copy()
        self._email_sent_at: dict[str, datetime] = {}

    async def run(self):
        self.logger.info("ops_starting")
        check_task = asyncio.create_task(self._check_loop())
        subscribe_task = asyncio.create_task(self._subscribe_loop())
        await asyncio.gather(check_task, subscribe_task)

    async def _subscribe_loop(self):
        async for msg in self.bus.subscribe("ops.heartbeat"):
            agent_name = msg.get("agent")
            if not agent_name:
                continue
            self._last_seen[agent_name] = datetime.now(timezone.utc)
            status = msg.get("status", "healthy")
            now = datetime.now(timezone.utc)
            await self.db.execute(
                """
                INSERT INTO agent_health (time, agent, status, metadata)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (agent) DO UPDATE SET time=$1, status=$3, metadata=$4
                """,
                now, agent_name, status, '{}',
            )

    async def _check_loop(self):
        while self._running:
            await self._check_agents()
            await asyncio.sleep(self.interval_seconds)

    async def _check_agents(self):
        now = datetime.now(timezone.utc)
        for agent_name, interval in self._known_agents.items():
            last = self._last_seen.get(agent_name)
            if last is None:
                continue

            gap = (now - last).total_seconds()
            if gap > 5 * interval:
                await self._write_health(agent_name, "down", gap)
                await self._maybe_alert(agent_name, gap)
            elif gap > 2 * interval:
                await self._write_health(agent_name, "degraded", gap)

    async def _write_health(self, agent_name: str, status: str, gap_seconds: float):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO agent_health (time, agent, status, metadata)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (agent) DO UPDATE SET time=$1, status=$3, metadata=$4
            """,
            now, agent_name, status, f'{{"gap_seconds": {gap_seconds:.0f}}}',
        )
        self.logger.warning("agent_health_changed", agent=agent_name, status=status, gap=gap_seconds)

    async def _maybe_alert(self, agent_name: str, gap_seconds: float):
        if not settings.gmail_sender:
            return
        last_sent = self._email_sent_at.get(agent_name)
        now = datetime.now(timezone.utc)
        if last_sent and (now - last_sent).total_seconds() < 3600:
            return

        self._email_sent_at[agent_name] = now
        subject = f"[HedgeFund] Agent DOWN: {agent_name}"
        body = f"Agent '{agent_name}' has not sent a heartbeat for {gap_seconds:.0f} seconds."
        self._send_email(subject, body)

    def _send_email(self, subject: str, body: str):
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = settings.gmail_sender
            msg["To"] = settings.gmail_sender
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(settings.gmail_sender, settings.gmail_sender)
                server.send_message(msg)
        except Exception as exc:
            self.logger.error("email_failed", error=str(exc))

    async def run_once(self):
        await self._check_agents()
```

Create `agents/ops/main.py`:

```python
#!/usr/bin/env python3
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.ops.agent import OpsAgent


async def main():
    bus = RedisBus(settings.redis_url)
    db = Database(settings.db_dsn)
    router = ModelRouter(
        primary=settings.ollama_primary_model,
        shadow=settings.ollama_shadow_model,
        host=settings.ollama_host,
        research_model=settings.ollama_research_model,
    )
    await bus.connect()
    await db.connect()
    agent = OpsAgent(name="ops", bus=bus, db=db, router=router, interval_seconds=60)
    try:
        await agent.run()
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```
.venv\Scripts\pytest tests/agents/ops/test_agent.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```
git add agents/ops/ tests/agents/ops/
git commit -m "feat: OpsAgent with heartbeat monitoring, degraded/down detection, Gmail alerts"
```

---

## Task 12: Final wiring + push

**Files:**
- Modify: `scripts/start_all.py`

- [ ] **Step 1: Update `scripts/start_all.py` to include all Phase 4b agents**

Replace the `AGENTS` list in `scripts/start_all.py` with:

```python
AGENTS: list[str] = [
    # Phase 2: Data ingest
    "data/ingest/main.py",
    # Phase 3: AI analysis
    "agents/technical/main.py",
    "agents/sentiment/main.py",
    "agents/macro/main.py",
    "agents/research/main.py",
    "agents/aggregator/main.py",
    # Phase 4a: Quant signal layer
    "agents/quant/momentum/main.py",
    "agents/quant/mean_reversion/main.py",
    "agents/quant/ml_quant/main.py",
    "agents/quant/supervisor/main.py",
    # Phase 4b: Portfolio execution layer
    "agents/portfolio_mgr/main.py",
    "agents/risk/main.py",
    "agents/execution/main.py",
    "agents/cio/main.py",
    "agents/ops/main.py",
]
```

- [ ] **Step 2: Run full test suite**

```
cd C:\Users\jomik\hedge-fund
.venv\Scripts\pytest tests/ -v --tb=short
```

Expected: all tests pass (existing ~105 + ~18 new = ~123 total)

- [ ] **Step 3: Commit and push**

```
git add scripts/start_all.py
git commit -m "feat: wire all Phase 4b agents into start_all.py"
git push origin master
```

---

## Self-Review

**Spec coverage:**
- ✅ RiskChecker: position size, open positions count, drawdown, VaR (30-day historical simulation, 5-min Redis cache), correlation (pairwise Pearson > 0.7, max 3 correlated)
- ✅ RiskAgent: 2-min poll, drawdown monitor, force-closes largest losing position, logs to `risk_events`
- ✅ PortfolioManagerAgent: aggregator (0.60) + quant_supervisor (0.40) weighting, Kelly sizing, CIO directive handling (low_conviction, avoid_open, request_close), PM re-analysis on request_close, crypto long-only, no pyramiding, sync RiskChecker validation
- ✅ ExecutionAgent: 5s poll, paper mode (latest DB close price), live mode (Alpaca stocks, Binance crypto), one retry after 2s, `status='failed'` on second failure, full position + portfolio_state updates in sequence
- ✅ CIOAgent: 1h interval, full data intake (24h signals, positions with P&L, 7d closed trades, macro regime, risk events, cio_override signals), LLM prompt → JSON directives, Redis set with 25h TTL, daily_brief signal written, malformed JSON handled gracefully, PM pushback noted (no re-escalation)
- ✅ OpsAgent: subscribes to `ops.heartbeat` in dedicated coroutine + 60s check loop, degraded at 2× interval, down at 5× interval, `agent_health` upsert on every heartbeat + status change, Gmail alert once per agent per hour via `smtplib`
- ✅ start_all.py: all 5 Phase 4b agents added

**No placeholders:** All code complete in all steps.

**Type consistency:**
- `RiskChecker.validate(symbol, direction, quantity, price, portfolio_value, peak_value, open_position_count, open_symbols, db, bus) -> tuple[bool, str]` — same signature used in both Task 6 implementation and Task 8 PM call
- `PortfolioManagerAgent._write_trade(symbol, direction, quantity, price, portfolio_value, reasoning, confidence)` — test assertion at `call[0][7]` (8th arg) for confidence matches the 7-arg signature (idx 0 = time, 1 = symbol, 2 = direction, 3 = quantity, 4 = paper, 5 = reasoning, 6 = confidence)
- `store_signal()` called with keyword args throughout — consistent with `agents/base.py` signature
- `OpsAgent.run()` overrides `BaseAgent.run()` entirely (no `super().run()`) — its own gather loop handles heartbeat subscription + check loop concurrently
