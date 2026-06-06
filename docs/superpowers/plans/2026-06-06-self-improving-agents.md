# Self-Improving Agents Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a closed-loop reinforcement system that tracks signal accuracy, adjusts agent parameters per market regime, monitors Jensen's Alpha against SPY, and surfaces everything (alpha tier, regime, proposals, history) in a new Intelligence dashboard tab.

**Architecture:** `AgentOptimizer` (24h cycle) reads `signal_outcomes` table, computes per-agent accuracy per regime, auto-applies small param changes to `agent_params.yaml`, and creates DB proposals for large changes. `AlphaMonitor` (daily) computes beta + Jensen's Alpha + Sharpe and sets the alpha tier in Redis. Extended macro agent detects `crisis` and `pandemic` regimes. New `/intelligence` gateway router + dashboard tab shows everything in real-time.

**Tech Stack:** Python asyncio, NumPy, asyncpg, Redis, PyYAML, FastAPI, Next.js 14, Tailwind, SWR

---

## File Structure

```
agents/optimizer/__init__.py              NEW
agents/optimizer/agent.py                NEW — AgentOptimizer (24h cycle)
agents/optimizer/alpha_monitor.py        NEW — AlphaMonitor (daily)
agents/optimizer/main.py                 NEW
agent_params.yaml                        NEW — regime-aware parameter store
shared/agent_params.py                   ALREADY CREATED in quant-strategies plan
agents/macro/agent.py                    MODIFY — add crisis/pandemic detection
agents/aggregator/agent.py               MODIFY — read agent weights from agent_params.yaml
gateway/routers/intelligence.py          NEW — 7 endpoints
dashboard/app/intelligence/page.tsx       NEW
dashboard/components/intelligence/
  alpha-status.tsx                        NEW
  regime-card.tsx                         NEW
  accuracy-table.tsx                      NEW
  params-view.tsx                         NEW
  proposals-list.tsx                      NEW
  history-log.tsx                         NEW
  strategies-list.tsx                     NEW
dashboard/components/layout/sidebar.tsx   MODIFY — add Intelligence nav entry
gateway/main.py                           MODIFY — register intelligence router
scripts/setup_db.py                       MODIFY — add 3 new tables
scripts/start_all.py                      MODIFY — add optimizer agent
tests/agents/optimizer/test_optimizer.py  NEW
tests/agents/optimizer/test_alpha_monitor.py  NEW
tests/gateway/test_intelligence.py        NEW
```

---

## Task 1: DB tables + agent_params.yaml

**Files:**
- Modify: `scripts/setup_db.py`
- Create: `agent_params.yaml`

- [ ] **Step 1: Add tables to setup_db.py**

In the `SCHEMA` string in `scripts/setup_db.py`, add before the final `CREATE OR REPLACE FUNCTION`:

```sql
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT NOT NULL,
    symbol          TEXT,
    signal_type     TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    regime          TEXT NOT NULL DEFAULT 'unknown',
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    pnl             DOUBLE PRECISION,
    was_correct     BOOLEAN,
    horizon_candles INTEGER
);
SELECT create_hypertable('signal_outcomes', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS signal_outcomes_agent_regime ON signal_outcomes(agent, regime, time DESC);

CREATE TABLE IF NOT EXISTS optimizer_proposals (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT NOT NULL,
    regime          TEXT NOT NULL,
    param_name      TEXT NOT NULL,
    current_value   DOUBLE PRECISION,
    proposed_value  DOUBLE PRECISION,
    change_pct      DOUBLE PRECISION,
    reason          TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',
    reviewed_at     TIMESTAMPTZ,
    reviewed_by     TEXT
);

CREATE TABLE IF NOT EXISTS optimizer_history (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent           TEXT,
    regime          TEXT,
    param_name      TEXT,
    old_value       DOUBLE PRECISION,
    new_value       DOUBLE PRECISION,
    reason          TEXT,
    auto_applied    BOOLEAN DEFAULT TRUE
);
SELECT create_hypertable('optimizer_history', 'time', if_not_exists => TRUE);
```

- [ ] **Step 2: Apply migration**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -c "
import asyncio, asyncpg, sys
sys.path.insert(0, '.')
from shared.config import settings

SQL = '''
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id BIGSERIAL PRIMARY KEY, time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent TEXT NOT NULL, symbol TEXT, signal_type TEXT NOT NULL,
    confidence DOUBLE PRECISION, regime TEXT NOT NULL DEFAULT 'unknown',
    entry_price DOUBLE PRECISION, exit_price DOUBLE PRECISION,
    pnl DOUBLE PRECISION, was_correct BOOLEAN, horizon_candles INTEGER
);
CREATE TABLE IF NOT EXISTS optimizer_proposals (
    id BIGSERIAL PRIMARY KEY, time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent TEXT NOT NULL, regime TEXT NOT NULL, param_name TEXT NOT NULL,
    current_value DOUBLE PRECISION, proposed_value DOUBLE PRECISION,
    change_pct DOUBLE PRECISION, reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_at TIMESTAMPTZ, reviewed_by TEXT
);
CREATE TABLE IF NOT EXISTS optimizer_history (
    id BIGSERIAL PRIMARY KEY, time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent TEXT, regime TEXT, param_name TEXT,
    old_value DOUBLE PRECISION, new_value DOUBLE PRECISION,
    reason TEXT, auto_applied BOOLEAN DEFAULT TRUE
);
'''
async def main():
    conn = await asyncpg.connect(settings.db_dsn)
    await conn.execute(SQL)
    await conn.close()
    print('Optimizer tables created.')
asyncio.run(main())
"
```

- [ ] **Step 3: Create `agent_params.yaml`**

```yaml
# agent_params.yaml
# Managed by AgentOptimizer. Do not edit manually while agents are running.

_meta:
  last_updated: "2026-06-06T00:00:00Z"
  optimizer_version: 1
  alpha_tier: learning

news_momentum:
  _default: &nm_default
    sentiment_weight: 0.40
    momentum_weight: 0.60
    composite_threshold: 1.0
    momentum_lookback: 20
    sentiment_lookback_hours: 2
  expansion: *nm_default
  contraction:
    sentiment_weight: 0.60
    momentum_weight: 0.40
    composite_threshold: 2.0
    momentum_lookback: 20
    sentiment_lookback_hours: 2
  crisis:
    sentiment_weight: 0.70
    momentum_weight: 0.30
    composite_threshold: 3.0
    momentum_lookback: 10
    sentiment_lookback_hours: 1
  pandemic:
    sentiment_weight: 0.80
    momentum_weight: 0.20
    composite_threshold: 4.0
    momentum_lookback: 5
    sentiment_lookback_hours: 1
  stagflation: *nm_default
  hiking_cycle: *nm_default
  cutting_cycle: *nm_default

vwap:
  _default: &vwap_default
    deviation_threshold_pct: 1.5
    min_candles: 5
    crypto_window_hours: 24
  expansion: *vwap_default
  contraction:
    deviation_threshold_pct: 2.5
    min_candles: 10
    crypto_window_hours: 24
  crisis:
    deviation_threshold_pct: 4.0
    min_candles: 15
    crypto_window_hours: 12
  pandemic:
    deviation_threshold_pct: 5.0
    min_candles: 20
    crypto_window_hours: 6
  stagflation: *vwap_default
  hiking_cycle: *vwap_default
  cutting_cycle: *vwap_default

aggregator:
  _default:
    agent_weights:
      technical: 1.0
      sentiment: 1.0
      macro: 1.0
      research: 1.0
      news_momentum: 1.0
      vwap: 1.0
      kronos: 1.0
  expansion:
    agent_weights:
      technical: 1.0
      sentiment: 1.0
      macro: 1.0
      research: 1.0
      news_momentum: 1.0
      vwap: 1.0
      kronos: 1.0
  crisis:
    agent_weights:
      technical: 0.5
      sentiment: 1.5
      macro: 2.0
      research: 0.8
      news_momentum: 1.0
      vwap: 0.3
      kronos: 1.2
  pandemic:
    agent_weights:
      technical: 0.3
      sentiment: 2.0
      macro: 2.5
      research: 1.0
      news_momentum: 0.8
      vwap: 0.2
      kronos: 1.5
```

- [ ] **Step 4: Commit**

```powershell
git add scripts/setup_db.py agent_params.yaml
git commit -m "feat(optimizer): add signal_outcomes, optimizer_proposals, optimizer_history tables + agent_params.yaml"
```

---

## Task 2: AgentOptimizer

**Files:**
- Create: `agents/optimizer/__init__.py`
- Create: `agents/optimizer/agent.py`
- Create: `tests/agents/optimizer/test_optimizer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/optimizer/test_optimizer.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import tempfile, os, yaml


def make_optimizer(yaml_path=None):
    from agents.optimizer.agent import AgentOptimizer
    agent = AgentOptimizer.__new__(AgentOptimizer)
    agent.name = "optimizer"
    agent.db = AsyncMock()
    agent.bus = AsyncMock()
    agent.logger = MagicMock()
    agent._running = True
    agent.interval_seconds = 86400
    agent.params_path = yaml_path or "agent_params.yaml"
    return agent


@pytest.mark.asyncio
async def test_compute_accuracy_returns_correct_ratio():
    from agents.optimizer.agent import AgentOptimizer
    agent = make_optimizer()
    agent.db.fetch = AsyncMock(return_value=[
        {"was_correct": True, "pnl": 50.0},
        {"was_correct": True, "pnl": 30.0},
        {"was_correct": False, "pnl": -20.0},
        {"was_correct": False, "pnl": -10.0},
    ])
    accuracy, avg_pnl = await agent._compute_accuracy("technical", "expansion")
    assert accuracy == 0.5
    assert avg_pnl == 12.5


@pytest.mark.asyncio
async def test_small_change_auto_applied(tmp_path):
    yaml_content = {
        "vwap": {"expansion": {"deviation_threshold_pct": 1.5}},
        "_meta": {"alpha_tier": "learning"}
    }
    params_file = tmp_path / "agent_params.yaml"
    params_file.write_text(yaml.dump(yaml_content))

    agent = make_optimizer(str(params_file))
    agent.db.execute = AsyncMock()

    await agent._apply_change(
        agent_name="vwap", regime="expansion",
        param_name="deviation_threshold_pct",
        current_val=1.5, new_val=1.6,
        reason="accuracy below threshold"
    )

    updated = yaml.safe_load(params_file.read_text())
    assert updated["vwap"]["expansion"]["deviation_threshold_pct"] == 1.6
    agent.db.execute.assert_called_once()  # optimizer_history insert


@pytest.mark.asyncio
async def test_large_change_creates_proposal():
    agent = make_optimizer()
    agent.db.execute = AsyncMock()

    await agent._propose_change(
        agent_name="vwap", regime="expansion",
        param_name="deviation_threshold_pct",
        current_val=1.5, new_val=3.0,
        reason="accuracy 35% over 30d"
    )

    agent.db.execute.assert_called_once()
    sql = agent.db.execute.call_args[0][0]
    assert "optimizer_proposals" in sql


@pytest.mark.asyncio
async def test_alpha_tier_locked_params_not_changed(tmp_path):
    yaml_content = {
        "vwap": {"expansion": {"deviation_threshold_pct": 1.5}},
        "_meta": {"alpha_tier": "exceptional_alpha"}
    }
    params_file = tmp_path / "agent_params.yaml"
    params_file.write_text(yaml.dump(yaml_content))

    agent = make_optimizer(str(params_file))
    agent.db.fetch = AsyncMock(return_value=[
        {"was_correct": False, "pnl": -50.0} for _ in range(10)
    ])
    agent.db.execute = AsyncMock()

    await agent._optimize_agent("vwap", "expansion")

    # With exceptional_alpha tier, no changes should be applied
    updated = yaml.safe_load(params_file.read_text())
    assert updated["vwap"]["expansion"]["deviation_threshold_pct"] == 1.5
```

- [ ] **Step 2: Run to verify fails**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/agents/optimizer/test_optimizer.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `agents/optimizer/__init__.py`**

```python
# agents/optimizer/__init__.py
```

- [ ] **Step 4: Create `agents/optimizer/agent.py`**

```python
# agents/optimizer/agent.py
"""
AgentOptimizer — runs every 24h.
Reads signal_outcomes, computes per-agent accuracy per regime,
auto-applies small param changes (<=10%) to agent_params.yaml,
creates DB proposals for large changes (>10%).
Respects alpha_tier: does nothing in exceptional_alpha, micro-adjustments only in alpha_achieved.
"""
import yaml
from shared.agent_base import BaseAgent

TUNABLE_PARAMS = {
    "vwap": {
        "expansion":   {"deviation_threshold_pct": (0.5, 4.0)},
        "contraction": {"deviation_threshold_pct": (1.0, 5.0)},
        "crisis":      {"deviation_threshold_pct": (2.0, 6.0)},
        "pandemic":    {"deviation_threshold_pct": (3.0, 8.0)},
    },
    "news_momentum": {
        "expansion":   {"composite_threshold": (0.5, 3.0), "sentiment_weight": (0.2, 0.8)},
        "contraction": {"composite_threshold": (1.0, 4.0), "sentiment_weight": (0.3, 0.9)},
        "crisis":      {"composite_threshold": (2.0, 5.0), "sentiment_weight": (0.5, 0.95)},
        "pandemic":    {"composite_threshold": (3.0, 6.0), "sentiment_weight": (0.6, 0.95)},
    },
}

MIN_SAMPLES = 10
POOR_ACCURACY_THRESHOLD = 0.45
AUTO_APPLY_MAX_CHANGE_PCT = 0.10


class AgentOptimizer(BaseAgent):
    def __init__(self, *args, params_path: str = "agent_params.yaml", **kwargs):
        super().__init__(*args, **kwargs)
        self.params_path = params_path

    async def run_once(self):
        alpha_tier = await self._get_alpha_tier()
        if alpha_tier == "exceptional_alpha":
            self.logger.info("optimizer_skipping_exceptional_alpha")
            return

        learning_rate = 0.10 if alpha_tier == "alpha_achieved" else 1.0
        active_regimes = await self._get_active_regimes()

        for agent_name, regime_params in TUNABLE_PARAMS.items():
            for regime in active_regimes:
                if regime in regime_params:
                    await self._optimize_agent(agent_name, regime, learning_rate)

    async def _get_alpha_tier(self) -> str:
        data = await self.bus.get("alpha:status") or {}
        return data.get("tier", "learning")

    async def _get_active_regimes(self) -> list[str]:
        rows = await self.db.fetch(
            "SELECT DISTINCT regime FROM signal_outcomes "
            "WHERE time > now() - INTERVAL '30 days'"
        )
        return [r["regime"] for r in rows] or ["expansion"]

    async def _compute_accuracy(self, agent_name: str, regime: str) -> tuple[float, float]:
        rows = await self.db.fetch(
            """
            SELECT was_correct, pnl FROM signal_outcomes
            WHERE agent = $1 AND regime = $2
              AND time > now() - INTERVAL '30 days'
              AND was_correct IS NOT NULL
            """,
            agent_name, regime,
        )
        if len(rows) < MIN_SAMPLES:
            return 0.5, 0.0
        accuracy = sum(1 for r in rows if r["was_correct"]) / len(rows)
        avg_pnl = sum(float(r["pnl"] or 0) for r in rows) / len(rows)
        return accuracy, avg_pnl

    async def _optimize_agent(self, agent_name: str, regime: str, learning_rate: float = 1.0):
        accuracy, avg_pnl = await self._compute_accuracy(agent_name, regime)
        if accuracy > POOR_ACCURACY_THRESHOLD and avg_pnl >= 0:
            return  # Agent performing adequately

        params = TUNABLE_PARAMS[agent_name].get(regime, {})
        current_config = self._read_param(agent_name, regime)

        for param_name, (min_val, max_val) in params.items():
            current_val = float(current_config.get(param_name, (min_val + max_val) / 2))
            # Increase threshold when accuracy is poor (makes agent more selective)
            adjustment = current_val * 0.05 * learning_rate
            new_val = min(max_val, max(min_val, current_val + adjustment))

            if new_val == current_val:
                continue

            change_pct = abs(new_val - current_val) / current_val if current_val != 0 else 1.0
            reason = (
                f"accuracy={accuracy:.1%}, avg_pnl=${avg_pnl:.2f} over last 30d in {regime} regime"
            )

            if change_pct <= AUTO_APPLY_MAX_CHANGE_PCT:
                await self._apply_change(agent_name, regime, param_name, current_val, new_val, reason)
            else:
                await self._propose_change(agent_name, regime, param_name, current_val, new_val, reason)

    def _read_param(self, agent_name: str, regime: str) -> dict:
        try:
            with open(self.params_path) as f:
                data = yaml.safe_load(f) or {}
            return data.get(agent_name, {}).get(regime, {})
        except FileNotFoundError:
            return {}

    async def _apply_change(self, agent_name: str, regime: str, param_name: str,
                            current_val: float, new_val: float, reason: str):
        try:
            with open(self.params_path) as f:
                data = yaml.safe_load(f) or {}
            data.setdefault(agent_name, {}).setdefault(regime, {})[param_name] = round(new_val, 6)
            with open(self.params_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception as exc:
            self.logger.error("optimizer_yaml_write_failed", error=str(exc))
            return

        await self.db.execute(
            "INSERT INTO optimizer_history (agent, regime, param_name, old_value, new_value, reason, auto_applied) "
            "VALUES ($1, $2, $3, $4, $5, $6, TRUE)",
            agent_name, regime, param_name, current_val, new_val, reason,
        )
        self.logger.info("optimizer_auto_applied", agent=agent_name, regime=regime,
                         param=param_name, old=current_val, new=new_val)

    async def _propose_change(self, agent_name: str, regime: str, param_name: str,
                              current_val: float, new_val: float, reason: str):
        change_pct = abs(new_val - current_val) / current_val * 100 if current_val != 0 else 100.0
        await self.db.execute(
            "INSERT INTO optimizer_proposals "
            "(agent, regime, param_name, current_value, proposed_value, change_pct, reason, status) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 'pending')",
            agent_name, regime, param_name, current_val, new_val, round(change_pct, 2), reason,
        )
        await self.bus.publish("optimizer.proposal", {
            "agent": agent_name, "regime": regime, "param": param_name,
            "current": current_val, "proposed": new_val, "reason": reason,
        })
        self.logger.info("optimizer_proposal_created", agent=agent_name, param=param_name,
                         change_pct=round(change_pct, 2))
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/optimizer/test_optimizer.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```powershell
git add agents/optimizer/__init__.py agents/optimizer/agent.py tests/agents/optimizer/test_optimizer.py
git commit -m "feat(optimizer): AgentOptimizer with regime-aware auto-tuning and CIO proposals"
```

---

## Task 3: AlphaMonitor (Jensen's Alpha + beta + tier management)

**Files:**
- Create: `agents/optimizer/alpha_monitor.py`
- Create: `tests/agents/optimizer/test_alpha_monitor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/agents/optimizer/test_alpha_monitor.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def make_monitor():
    from agents.optimizer.alpha_monitor import AlphaMonitor
    m = AlphaMonitor.__new__(AlphaMonitor)
    m.name = "alpha_monitor"
    m.db = AsyncMock()
    m.bus = AsyncMock()
    m.logger = MagicMock()
    m._running = True
    m.interval_seconds = 86400
    m.write_to_obsidian = AsyncMock()
    return m


def _make_price_rows(prices: list[float], symbol: str = "SPY"):
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    return [
        {"total_value": p, "time": (now - timedelta(days=len(prices) - i)).isoformat()}
        for i, p in enumerate(prices)
    ]


@pytest.mark.asyncio
async def test_beta_computation():
    from agents.optimizer.alpha_monitor import _compute_beta
    # Portfolio goes up 2x when SPY goes up 1x → beta ≈ 2
    portfolio = [100, 102, 104, 106, 108, 110]
    spy = [100, 101, 102, 103, 104, 105]
    beta = _compute_beta(portfolio, spy)
    assert abs(beta - 2.0) < 0.1


@pytest.mark.asyncio
async def test_jensens_alpha_positive():
    from agents.optimizer.alpha_monitor import _compute_jensens_alpha
    # Portfolio annualised +20%, SPY +10%, beta=1.0 → alpha = 10%
    alpha = _compute_jensens_alpha(
        portfolio_annual_return=0.20,
        spy_annual_return=0.10,
        beta=1.0
    )
    assert abs(alpha - 0.10) < 0.001


@pytest.mark.asyncio
async def test_tier_transitions_to_alpha_achieved():
    monitor = make_monitor()
    monitor.bus.get = AsyncMock(return_value={"tier": "learning"})
    monitor.bus.set = AsyncMock()
    monitor.bus.publish = AsyncMock()
    # Portfolio values showing consistent growth
    portfolio_vals = [100000 + i * 500 for i in range(31)]
    spy_vals = [100 + i * 0.1 for i in range(31)]

    with patch("agents.optimizer.alpha_monitor._compute_sharpe", return_value=1.6), \
         patch("agents.optimizer.alpha_monitor._compute_jensens_alpha", return_value=0.03):
        await monitor._classify_and_act(
            sharpe=1.6, jensens_alpha=0.03, beta=0.9,
            portfolio_annual=0.15, spy_annual=0.10
        )

    monitor.bus.set.assert_called()
    set_call = monitor.bus.set.call_args
    assert set_call[0][0] == "alpha:status"
    assert set_call[0][1]["tier"] == "alpha_achieved"


@pytest.mark.asyncio
async def test_exceptional_alpha_saves_strategy_to_obsidian():
    monitor = make_monitor()
    monitor.bus.get = AsyncMock(return_value={"tier": "alpha_achieved"})
    monitor.bus.set = AsyncMock()
    monitor.bus.publish = AsyncMock()

    with patch("agents.optimizer.alpha_monitor._compute_sharpe", return_value=2.2), \
         patch("agents.optimizer.alpha_monitor._compute_jensens_alpha", return_value=0.06):
        await monitor._classify_and_act(
            sharpe=2.2, jensens_alpha=0.06, beta=0.8,
            portfolio_annual=0.25, spy_annual=0.12
        )

    monitor.write_to_obsidian.assert_called_once()
    call = monitor.write_to_obsidian.call_args
    assert "exceptional" in call.kwargs["title"].lower() or "Exceptional" in call.kwargs["title"]
```

- [ ] **Step 2: Run to verify fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/optimizer/test_alpha_monitor.py -v
```

Expected: `ModuleNotFoundError`

- [ ] **Step 3: Create `agents/optimizer/alpha_monitor.py`**

```python
# agents/optimizer/alpha_monitor.py
import math
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.memory import MemoryMixin


def _daily_returns(values: list[float]) -> list[float]:
    return [(values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values)) if values[i - 1] != 0]


def _compute_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    std = math.sqrt(sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1))
    return (mean / std) * math.sqrt(252) if std > 0 else 0.0


def _compute_beta(portfolio_values: list[float], spy_values: list[float]) -> float:
    port_ret = _daily_returns(portfolio_values)
    spy_ret = _daily_returns(spy_values)
    n = min(len(port_ret), len(spy_ret))
    if n < 2:
        return 1.0
    port_ret, spy_ret = port_ret[-n:], spy_ret[-n:]
    mean_p = sum(port_ret) / n
    mean_s = sum(spy_ret) / n
    cov = sum((port_ret[i] - mean_p) * (spy_ret[i] - mean_s) for i in range(n)) / (n - 1)
    var_s = sum((r - mean_s) ** 2 for r in spy_ret) / (n - 1)
    return cov / var_s if var_s > 0 else 1.0


def _compute_jensens_alpha(portfolio_annual_return: float,
                           spy_annual_return: float,
                           beta: float) -> float:
    return portfolio_annual_return - (beta * spy_annual_return)


class AlphaMonitor(MemoryMixin, BaseAgent):
    async def run_once(self):
        # Fetch 30d of portfolio state
        port_rows = await self.db.fetch(
            "SELECT total_value, time FROM portfolio_state "
            "WHERE time > now() - INTERVAL '30 days' ORDER BY time ASC"
        )
        # Fetch 30d of SPY prices
        spy_rows = await self.db.fetch(
            "SELECT close, time FROM prices WHERE symbol = 'SPY' "
            "AND time > now() - INTERVAL '30 days' ORDER BY time ASC"
        )

        if len(port_rows) < 5 or len(spy_rows) < 5:
            self.logger.info("alpha_monitor_insufficient_data")
            return

        port_vals = [float(r["total_value"]) for r in port_rows]
        spy_vals = [float(r["close"]) for r in spy_rows]

        port_daily = _daily_returns(port_vals)
        spy_daily = _daily_returns(spy_vals)
        sharpe = _compute_sharpe(port_daily)
        beta = _compute_beta(port_vals, spy_vals)

        # Annualised returns
        days = max((datetime.fromisoformat(str(port_rows[-1]["time"])) -
                    datetime.fromisoformat(str(port_rows[0]["time"]))).days, 1)
        port_annual = (port_vals[-1] / port_vals[0]) ** (365 / days) - 1
        spy_annual = (spy_vals[-1] / spy_vals[0]) ** (365 / days) - 1
        jensens_alpha = _compute_jensens_alpha(port_annual, spy_annual, beta)

        await self._classify_and_act(sharpe, jensens_alpha, beta, port_annual, spy_annual)

    async def _classify_and_act(self, sharpe: float, jensens_alpha: float,
                                beta: float, portfolio_annual: float, spy_annual: float):
        prev = await self.bus.get("alpha:status") or {}
        prev_tier = prev.get("tier", "learning")

        # Determine new tier
        if sharpe >= 2.0 and jensens_alpha >= 0.05:
            tier = "exceptional_alpha"
        elif sharpe >= 1.5 and jensens_alpha >= 0.02:
            tier = "alpha_achieved"
        else:
            tier = "learning"

        status = {
            "tier": tier,
            "sharpe": round(sharpe, 4),
            "jensens_alpha": round(jensens_alpha * 100, 4),  # stored as %
            "beta": round(beta, 4),
            "portfolio_annual_pct": round(portfolio_annual * 100, 2),
            "spy_annual_pct": round(spy_annual * 100, 2),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.bus.set("alpha:status", status)

        if tier != prev_tier:
            self.logger.info("alpha_tier_changed", old=prev_tier, new=tier,
                             sharpe=sharpe, alpha_pct=round(jensens_alpha * 100, 2))
            if tier == "alpha_achieved" and prev_tier == "learning":
                await self.bus.publish("cio.daily_brief", {
                    "subject": "🎯 Alpha Achieved — Trading System Update",
                    "report": (
                        f"Alpha achieved!\n\n"
                        f"Sharpe: {sharpe:.2f} (threshold: 1.5)\n"
                        f"Jensen's Alpha: {jensens_alpha*100:.2f}% (threshold: 2%)\n"
                        f"Beta: {beta:.2f}\n"
                        f"Portfolio annual return: {portfolio_annual*100:.2f}%\n"
                        f"SPY annual return: {spy_annual*100:.2f}%\n\n"
                        f"Parameters are now locked. Micro-adjustments only."
                    ),
                })
            elif tier == "exceptional_alpha":
                await self._save_exceptional_strategy(status)
                await self.bus.publish("cio.daily_brief", {
                    "subject": "🏆 Exceptional Alpha Achieved — Strategy Locked",
                    "report": (
                        f"Exceptional alpha achieved!\n\n"
                        f"Sharpe: {sharpe:.2f} (threshold: 2.0)\n"
                        f"Jensen's Alpha: {jensens_alpha*100:.2f}% (threshold: 5%)\n"
                        f"Beta: {beta:.2f}\n"
                        f"All parameters fully locked. Strategy saved to Obsidian vault."
                    ),
                })
            elif tier == "learning" and prev_tier in ("alpha_achieved", "exceptional_alpha"):
                await self.bus.publish("cio.daily_brief", {
                    "subject": "⚠️ Alpha Eroded — Resuming Optimization",
                    "report": (
                        f"Alpha has eroded below thresholds.\n\n"
                        f"Sharpe: {sharpe:.2f}, Jensen's Alpha: {jensens_alpha*100:.2f}%\n"
                        f"Full optimization resumed."
                    ),
                })

    async def _save_exceptional_strategy(self, status: dict):
        now = datetime.now(timezone.utc)
        body = (
            f"## Exceptional Alpha Strategy\n\n"
            f"**Captured:** {now.isoformat()}\n"
            f"**Sharpe:** {status['sharpe']}\n"
            f"**Jensen's Alpha:** {status['jensens_alpha']}%\n"
            f"**Beta:** {status['beta']}\n\n"
            f"### Parameters\n\nSee current `agent_params.yaml` at this commit.\n"
        )
        await self.write_to_obsidian(
            title=f"Exceptional Alpha {now.strftime('%Y-%m-%d')}",
            body=body,
            tags=["alpha", "strategy", "exceptional"],
        )
```

- [ ] **Step 4: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/agents/optimizer/test_alpha_monitor.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Create `agents/optimizer/main.py`**

```python
# agents/optimizer/main.py
import asyncio
import sys
sys.path.insert(0, ".")
from shared.config import settings
from shared.bus import RedisBus
from shared.db import Database
from shared.model_router import ModelRouter
from agents.optimizer.agent import AgentOptimizer
from agents.optimizer.alpha_monitor import AlphaMonitor


async def run_optimizer():
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
    optimizer = AgentOptimizer(name="optimizer", bus=bus, db=db, router=router,
                               interval_seconds=86400)
    monitor = AlphaMonitor(name="alpha_monitor", bus=bus, db=db, router=router,
                           interval_seconds=86400)
    try:
        await asyncio.gather(optimizer.run(), monitor.run())
    finally:
        await bus.disconnect()
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(run_optimizer())
```

- [ ] **Step 6: Commit**

```powershell
git add agents/optimizer/ tests/agents/optimizer/
git commit -m "feat(optimizer): AlphaMonitor with Jensen's Alpha, beta, 3-tier classification + Obsidian snapshots"
```

---

## Task 4: Intelligence gateway router

**Files:**
- Create: `gateway/routers/intelligence.py`
- Create: `tests/gateway/test_intelligence.py`
- Modify: `gateway/main.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gateway/test_intelligence.py
import pytest


@pytest.mark.asyncio
async def test_intelligence_status_returns_tier(client, mock_bus):
    mock_bus.get = AsyncMock(return_value={
        "tier": "learning", "sharpe": 0.87, "jensens_alpha": 1.2,
        "beta": 0.94, "portfolio_annual_pct": 12.0, "spy_annual_pct": 10.0
    })
    resp = await client.get("/intelligence/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "learning"
    assert data["sharpe"] == 0.87


@pytest.mark.asyncio
async def test_intelligence_proposals_returns_pending(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "agent": "vwap", "regime": "expansion", "param_name": "deviation_threshold_pct",
         "current_value": 1.5, "proposed_value": 2.1, "change_pct": 40.0,
         "reason": "accuracy 38%", "status": "pending", "time": "2026-06-06T00:00:00+00:00"}
    ]
    resp = await client.get("/intelligence/proposals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["agent"] == "vwap"


@pytest.mark.asyncio
async def test_approve_proposal_updates_status(client, mock_db):
    mock_db.fetchrow = AsyncMock(return_value={
        "id": 1, "agent": "vwap", "regime": "expansion",
        "param_name": "deviation_threshold_pct", "proposed_value": 2.1, "status": "pending"
    })
    mock_db.execute = AsyncMock()
    resp = await client.post("/intelligence/proposals/1/approve")
    assert resp.status_code == 200
    mock_db.execute.assert_called()


@pytest.mark.asyncio
async def test_approve_nonexistent_proposal_returns_404(client, mock_db):
    mock_db.fetchrow = AsyncMock(return_value=None)
    resp = await client.post("/intelligence/proposals/999/approve")
    assert resp.status_code == 404
```

Add `from unittest.mock import AsyncMock` to top of test file.

- [ ] **Step 2: Run to verify fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_intelligence.py -v
```

Expected: 404 (route missing)

- [ ] **Step 3: Create `gateway/routers/intelligence.py`**

```python
# gateway/routers/intelligence.py
import yaml
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
        WHERE time > now() - INTERVAL '30 days'
          AND was_correct IS NOT NULL
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
    # Apply the change to agent_params.yaml
    try:
        with open("agent_params.yaml") as f:
            params = yaml.safe_load(f) or {}
        params.setdefault(row["agent"], {}).setdefault(row["regime"], {})[row["param_name"]] = row["proposed_value"]
        with open("agent_params.yaml", "w") as f:
            yaml.dump(params, f, default_flow_style=False)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to apply: {exc}")
    await db.execute(
        "UPDATE optimizer_proposals SET status = 'approved', reviewed_at = now(), reviewed_by = 'dashboard' WHERE id = $1",
        proposal_id
    )
    await db.execute(
        "INSERT INTO optimizer_history (agent, regime, param_name, old_value, new_value, reason, auto_applied) "
        "VALUES ($1, $2, $3, $4, $5, $6, FALSE)",
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
        "UPDATE optimizer_proposals SET status = 'rejected', reviewed_at = now(), reviewed_by = 'dashboard' WHERE id = $1",
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
    import os
    from pathlib import Path
    strategy_dir = Path("memory/obsidian/alpha_monitor")
    if not strategy_dir.exists():
        return []
    files = sorted(strategy_dir.glob("*.md"), reverse=True)
    result = []
    for f in files[:10]:
        result.append({"filename": f.name, "content": f.read_text(encoding="utf-8")})
    return result
```

- [ ] **Step 4: Register in gateway/main.py**

Add import:
```python
from gateway.routers import intelligence as intelligence_router
```

Add route:
```python
app.include_router(intelligence_router.router, prefix="/intelligence", tags=["intelligence"])
```

- [ ] **Step 5: Run tests — expect PASS**

```powershell
.venv\Scripts\python.exe -m pytest tests/gateway/test_intelligence.py -v
```

Expected: `4 passed`

- [ ] **Step 6: Commit**

```powershell
git add gateway/routers/intelligence.py gateway/main.py tests/gateway/test_intelligence.py
git commit -m "feat(intelligence): gateway router with status, accuracy, params, proposals, history, strategies"
```

---

## Task 5: Intelligence dashboard tab

**Files:**
- Create: `dashboard/app/intelligence/page.tsx`
- Create: `dashboard/components/intelligence/alpha-status.tsx`
- Create: `dashboard/components/intelligence/regime-card.tsx`
- Create: `dashboard/components/intelligence/accuracy-table.tsx`
- Create: `dashboard/components/intelligence/proposals-list.tsx`
- Create: `dashboard/components/intelligence/history-log.tsx`
- Modify: `dashboard/components/layout/sidebar.tsx`

- [ ] **Step 1: Create `dashboard/components/intelligence/alpha-status.tsx`**

```tsx
// dashboard/components/intelligence/alpha-status.tsx
"use client";

interface AlphaStatus {
  tier: string;
  sharpe: number;
  jensens_alpha: number;
  beta: number;
  portfolio_annual_pct: number;
  spy_annual_pct: number;
}

const TIER_CONFIG = {
  learning:          { label: "Learning",          color: "text-warning",  bg: "bg-warning/10",  border: "border-warning/20" },
  alpha_achieved:    { label: "Alpha Achieved",    color: "text-accent",   bg: "bg-accent/10",   border: "border-accent/20" },
  exceptional_alpha: { label: "Exceptional Alpha", color: "text-purple-400", bg: "bg-purple-400/10", border: "border-purple-400/20" },
};

export function AlphaStatus({ data }: { data: AlphaStatus | null }) {
  if (!data) return <div className="bg-surface border border-border rounded-xl p-5 h-32 animate-pulse" />;
  const tier = TIER_CONFIG[data.tier as keyof typeof TIER_CONFIG] || TIER_CONFIG.learning;

  return (
    <div className={`border rounded-xl p-5 ${tier.bg} ${tier.border}`}>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-muted uppercase tracking-widest">Alpha Status</h2>
        <span className={`text-sm font-bold px-3 py-1 rounded-full ${tier.bg} ${tier.color} border ${tier.border}`}>
          {tier.label}
        </span>
      </div>
      <div className="grid grid-cols-4 gap-4">
        {[
          { label: "Sharpe (30d)", value: data.sharpe.toFixed(2), threshold: "≥1.5" },
          { label: "Jensen's α", value: `${data.jensens_alpha.toFixed(2)}%`, threshold: "≥2%" },
          { label: "Beta", value: data.beta.toFixed(2), threshold: "" },
          { label: "Portfolio vs SPY", value: `${(data.portfolio_annual_pct - data.spy_annual_pct).toFixed(1)}%`, threshold: "excess" },
        ].map(({ label, value, threshold }) => (
          <div key={label} className="text-center">
            <p className="text-xs text-muted mb-1">{label} {threshold && <span className="opacity-60">({threshold})</span>}</p>
            <p className={`text-xl font-bold font-mono ${tier.color}`}>{value}</p>
          </div>
        ))}
      </div>
      <div className="mt-3 space-y-1">
        <div className="flex justify-between text-xs text-muted">
          <span>Sharpe progress</span><span>{data.sharpe.toFixed(2)} / 1.5</span>
        </div>
        <div className="bg-border rounded-full h-1.5">
          <div className="h-1.5 rounded-full bg-accent transition-all"
               style={{ width: `${Math.min(100, (data.sharpe / 1.5) * 100)}%` }} />
        </div>
        <div className="flex justify-between text-xs text-muted">
          <span>Jensen's α progress</span><span>{data.jensens_alpha.toFixed(2)}% / 2%</span>
        </div>
        <div className="bg-border rounded-full h-1.5">
          <div className="h-1.5 rounded-full bg-accent transition-all"
               style={{ width: `${Math.min(100, (data.jensens_alpha / 2) * 100)}%` }} />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `dashboard/components/intelligence/accuracy-table.tsx`**

```tsx
// dashboard/components/intelligence/accuracy-table.tsx
"use client";

interface AgentAccuracy {
  agent: string;
  signals: number;
  accuracy: number;
  avg_pnl: number;
}

export function AccuracyTable({ data }: { data: AgentAccuracy[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Agent Accuracy (30d, current regime)
      </h2>
      {data.length === 0 ? (
        <p className="text-muted text-sm">No signal outcomes recorded yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="text-muted text-xs border-b border-border">
              <th className="text-left py-2">Agent</th>
              <th className="text-right py-2">Signals</th>
              <th className="text-right py-2">Accuracy</th>
              <th className="text-right py-2">Avg P&L</th>
            </tr>
          </thead>
          <tbody>
            {data.map((row) => (
              <tr key={row.agent} className="border-b border-border/40 hover:bg-white/5">
                <td className="py-2 font-medium capitalize">{row.agent.replace(/_/g, " ")}</td>
                <td className="py-2 text-right font-mono text-muted">{row.signals}</td>
                <td className="py-2 text-right font-mono">
                  <span className={row.accuracy >= 0.5 ? "text-accent" : "text-danger"}>
                    {(row.accuracy * 100).toFixed(1)}%
                  </span>
                </td>
                <td className={`py-2 text-right font-mono ${row.avg_pnl >= 0 ? "text-accent" : "text-danger"}`}>
                  ${row.avg_pnl.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create `dashboard/components/intelligence/proposals-list.tsx`**

```tsx
// dashboard/components/intelligence/proposals-list.tsx
"use client";
import { apiFetch } from "@/lib/api";

interface Proposal {
  id: number;
  agent: string;
  regime: string;
  param_name: string;
  current_value: number;
  proposed_value: number;
  change_pct: number;
  reason: string;
  status: string;
  time: string;
}

interface ProposalsListProps {
  proposals: Proposal[];
  onReview: () => void;
}

export function ProposalsList({ proposals, onReview }: ProposalsListProps) {
  async function approve(id: number) {
    await apiFetch(`/intelligence/proposals/${id}/approve`, { method: "POST" });
    onReview();
  }
  async function reject(id: number) {
    await apiFetch(`/intelligence/proposals/${id}/reject`, { method: "POST" });
    onReview();
  }

  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Pending CIO Proposals
        {proposals.length > 0 && (
          <span className="ml-2 bg-warning/20 text-warning text-xs px-2 py-0.5 rounded-full">
            {proposals.length}
          </span>
        )}
      </h2>
      {proposals.length === 0 ? (
        <p className="text-muted text-sm">No pending proposals.</p>
      ) : (
        <div className="space-y-3">
          {proposals.map((p) => (
            <div key={p.id} className="border border-border rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-medium">{p.agent}</span>
                  <span className="text-muted mx-2">›</span>
                  <span className="text-muted">{p.regime}</span>
                  <span className="text-muted mx-2">›</span>
                  <span className="font-mono text-sm">{p.param_name}</span>
                </div>
                <span className={`text-xs font-mono ${p.change_pct > 0 ? "text-accent" : "text-danger"}`}>
                  {p.change_pct > 0 ? "+" : ""}{p.change_pct.toFixed(1)}%
                </span>
              </div>
              <div className="flex items-center gap-3 text-sm font-mono">
                <span className="text-muted">{p.current_value}</span>
                <span className="text-muted">→</span>
                <span className="text-accent">{p.proposed_value}</span>
              </div>
              <p className="text-xs text-muted">{p.reason}</p>
              <div className="flex gap-2 pt-1">
                <button onClick={() => approve(p.id)}
                  className="flex-1 py-1.5 rounded bg-accent/10 text-accent text-xs font-medium hover:bg-accent/20 transition-colors">
                  ✓ Approve
                </button>
                <button onClick={() => reject(p.id)}
                  className="flex-1 py-1.5 rounded bg-danger/10 text-danger text-xs font-medium hover:bg-danger/20 transition-colors">
                  ✗ Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create `dashboard/components/intelligence/history-log.tsx`**

```tsx
// dashboard/components/intelligence/history-log.tsx
"use client";

interface HistoryEntry {
  id: number;
  time: string;
  agent: string;
  regime: string;
  param_name: string;
  old_value: number;
  new_value: number;
  reason: string;
  auto_applied: boolean;
}

export function HistoryLog({ entries }: { entries: HistoryEntry[] }) {
  return (
    <div className="bg-surface border border-border rounded-xl p-5">
      <h2 className="text-sm font-semibold text-muted uppercase tracking-widest mb-4">
        Parameter Change History
      </h2>
      {entries.length === 0 ? (
        <p className="text-muted text-sm">No changes yet.</p>
      ) : (
        <div className="space-y-1 font-mono text-xs">
          {entries.map((e) => (
            <div key={e.id} className="flex gap-3 items-start border-b border-border/30 py-1.5">
              <span className="text-muted shrink-0 w-20">
                {new Date(e.time).toLocaleDateString()}
              </span>
              <span className={`shrink-0 w-4 ${e.auto_applied ? "text-accent" : "text-purple-400"}`}>
                {e.auto_applied ? "A" : "M"}
              </span>
              <span className="text-slate-300">
                {e.agent} › {e.regime} › {e.param_name}: {e.old_value} → {e.new_value}
              </span>
            </div>
          ))}
        </div>
      )}
      <p className="text-xs text-muted mt-2">A = auto-applied  M = manual approval</p>
    </div>
  );
}
```

- [ ] **Step 5: Create `dashboard/app/intelligence/page.tsx`**

```tsx
// dashboard/app/intelligence/page.tsx
"use client";
import useSWR from "swr";
import { apiFetch } from "@/lib/api";
import { AlphaStatus } from "@/components/intelligence/alpha-status";
import { AccuracyTable } from "@/components/intelligence/accuracy-table";
import { ProposalsList } from "@/components/intelligence/proposals-list";
import { HistoryLog } from "@/components/intelligence/history-log";

export default function IntelligencePage() {
  const { data: status } = useSWR("intelligence-status",
    () => apiFetch("/intelligence/status"), { refreshInterval: 30000 });

  const { data: accuracy = [] } = useSWR("intelligence-accuracy",
    () => apiFetch("/intelligence/accuracy"), { refreshInterval: 60000 });

  const { data: proposals = [], mutate: mutateProposals } = useSWR("intelligence-proposals",
    () => apiFetch("/intelligence/proposals"), { refreshInterval: 10000 });

  const { data: history = [] } = useSWR("intelligence-history",
    () => apiFetch("/intelligence/history"), { refreshInterval: 60000 });

  const { data: regimeData } = useSWR("macro-regime",
    () => apiFetch("/signals?limit=1"), { refreshInterval: 60000 });

  const currentRegime = (regimeData as any)?.[0]?.signal_type || "unknown";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Intelligence</h1>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted">Regime:</span>
          <span className="px-3 py-1 bg-accent/10 text-accent text-xs font-bold rounded-full uppercase">
            {currentRegime.replace(/_/g, " ")}
          </span>
        </div>
      </div>

      <AlphaStatus data={status} />

      <div className="grid grid-cols-2 gap-4">
        <AccuracyTable data={accuracy} />
        <ProposalsList proposals={proposals} onReview={mutateProposals} />
      </div>

      <HistoryLog entries={history} />
    </div>
  );
}
```

- [ ] **Step 6: Add Intelligence to sidebar**

In `dashboard/components/layout/sidebar.tsx`, add `Brain` to the imports:

```tsx
import {
  LayoutDashboard, Cpu, BarChart2, Activity,
  FlaskConical, Server, MessageSquare, ArrowLeftRight, BrainCircuit, TrendingUp, Brain
} from "lucide-react";
```

Add to NAV array after Analytics:
```tsx
{ href: "/intelligence", label: "Intelligence", icon: Brain },
```

- [ ] **Step 7: Register agent in start_all.py**

In `scripts/start_all.py`, add:
```python
    "agents/optimizer/main.py",
```

After the quant agents section.

- [ ] **Step 8: Run full test suite**

```powershell
Set-Location C:\Users\jomik\hedge-fund
.venv\Scripts\python.exe -m pytest tests/ --tb=no -q
```

Expected: all pass

- [ ] **Step 9: Commit**

```powershell
git add agents/optimizer/alpha_monitor.py agents/optimizer/main.py \
        gateway/routers/intelligence.py gateway/main.py \
        dashboard/app/intelligence/ dashboard/components/intelligence/ \
        dashboard/components/layout/sidebar.tsx \
        scripts/start_all.py
git commit -m "feat(intelligence): Intelligence dashboard tab + alpha monitor + optimizer agent fully wired"
```
