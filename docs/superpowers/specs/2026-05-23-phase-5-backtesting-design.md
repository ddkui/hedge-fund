# Phase 5 — Backtesting Engine Design

## Goal

Replay the existing agent pipeline against historical data to measure strategy performance (Sharpe, drawdown, win rate, CAGR) and produce an interactive HTML report with equity curve and trade log.

## Architecture

**Approach:** Agent replay — actual `run_once()` code executes against historical `prices`, `news_items`, and `macro_data`. No signal logic is reimplemented outside the agent framework.

**Time simulation:** PostgreSQL session variable `backtest.now`. A helper function `now_or_backtest()` is added to the DB schema and replaces `NOW()` in all agent SQL strings. In live mode the session variable is unset and the function returns `NOW()`. In backtest mode it returns the simulated tick time.

**Schema isolation:** Each run gets a dedicated PostgreSQL schema `bt_{run_id}`. `BacktestDB` sets `search_path = bt_{run_id}, public` on the connection. Agents read historical data from `public` (prices, news, macro) and write signals, trades, positions, and portfolio_state into the isolated schema. Runs never touch live tables.

**Clock:** Configurable step size (default 1 hour). `BacktestClock` yields `datetime` ticks from `start` to `end` at the configured interval, skipping nothing (weekends and market halts are handled naturally — agents find no price data and emit no signals).

**Agent execution order per tick (sequential tiers, parallel within tier):**
1. `technical`, `sentiment`, `macro`, `research` (parallel)
2. `aggregator`
3. `momentum`, `mean_reversion`, `ml_quant` (parallel)
4. `quant_supervisor`
5. `portfolio_mgr`
6. `risk`
7. `execution`

CIO and OpsAgent excluded by default. Any agent can be added or removed via `--agents` CLI flag.

**Bus:** `InMemoryBus` replaces Redis during backtest. `set/get` operate on a plain Python dict. `subscribe` is a no-op async generator. CIO directives persist in-memory across ticks within a run.

---

## Components

### `backtest/clock.py` — `BacktestClock`

Yields `datetime` ticks from `start` to `end` at `step_seconds` interval. Stateless iterator.

```python
class BacktestClock:
    def __init__(self, start: datetime, end: datetime, step_seconds: int): ...
    def ticks(self) -> Iterator[datetime]: ...
```

### `backtest/bus.py` — `InMemoryBus`

Drop-in replacement for `RedisBus` during backtest. Implements `set`, `get`, `publish`, `subscribe` against a plain dict. `subscribe` yields nothing.

```python
class InMemoryBus:
    async def set(self, key: str, value, ex: int | None = None): ...
    async def get(self, key: str): ...
    async def publish(self, channel: str, message): ...
    async def subscribe(self, channel: str) -> AsyncIterator: ...
    async def connect(self): ...
    async def disconnect(self): ...
```

### `backtest/db.py` — `BacktestDB`

Wraps the existing `Database` class. On `set_tick(dt)`, executes `SET backtest.now = '{dt}'` (session-level, persists across statements on the same connection). On `set_schema(run_id)`, sets `search_path = bt_{run_id}, public`.

```python
class BacktestDB:
    def __init__(self, dsn: str, run_id: int): ...
    async def connect(self): ...
    async def set_tick(self, dt: datetime): ...
    async def fetch(self, query: str, *args): ...
    async def fetchrow(self, query: str, *args): ...
    async def execute(self, query: str, *args): ...
```

### `backtest/runner.py` — `BacktestRunner`

Instantiates all selected agents with `BacktestDB` and `InMemoryBus`. Steps through `BacktestClock` ticks, calling `set_tick` then firing each agent tier in order. Writes initial `portfolio_state` row at tick 0: `cash=initial_capital, total_value=initial_capital, peak_value=initial_capital, open_positions=0`.

```python
class BacktestRunner:
    def __init__(self, run_id: int, clock: BacktestClock, db: BacktestDB,
                 bus: InMemoryBus, agent_names: list[str]): ...
    async def run(self): ...
    async def _fire_tier(self, agents: list[BaseAgent]): ...
```

### `backtest/metrics.py` — `compute_metrics`

Reads `portfolio_state` from `bt_{run_id}` schema. Returns a dict with:
- `total_return_pct`
- `cagr_pct`
- `sharpe_ratio` (annualized, rf=0)
- `max_drawdown_pct`
- `win_rate_pct` (from `trades`)
- `total_trades`
- `avg_trade_duration_hours`

```python
def compute_metrics(snapshots: list[dict], trades: list[dict]) -> dict: ...
```

### `backtest/report.py` — `ReportGenerator`

Reads results from `bt_{run_id}`, calls `compute_metrics`, renders a self-contained HTML file using `jinja2` + embedded `plotly` charts. No server required — output is a single `.html` file.

Charts included:
- Equity curve (total_value over time)
- Drawdown (% below peak)

Tables included:
- Key metrics summary
- Trade log (symbol, action, quantity, fill price, P&L per trade)
- Per-agent signal count

```python
class ReportGenerator:
    def __init__(self, db: BacktestDB, run_id: int): ...
    async def generate(self, output_path: str): ...
```

### `backtest/cli.py` — Entry point

```bash
python backtest/cli.py \
  --start 2024-01-01 \
  --end   2024-12-31 \
  --step  1h \
  --agents technical,sentiment,macro,research,aggregator,\
           momentum,mean_reversion,ml_quant,quant_supervisor,\
           portfolio_mgr,risk,execution \
  --output reports/backtest_2024.html
```

Parses args, creates `backtest_runs` row, runs `BacktestRunner`, calls `ReportGenerator`, prints summary metrics to stdout, updates `backtest_runs.status = 'done'`.

### `scripts/setup_backtest_db.py`

Creates:
1. `now_or_backtest()` SQL function in `public` schema
2. `backtest_runs` table in `public` schema

```sql
CREATE TABLE IF NOT EXISTS backtest_runs (
    id           SERIAL PRIMARY KEY,
    start_date   TIMESTAMPTZ NOT NULL,
    end_date     TIMESTAMPTZ NOT NULL,
    step_seconds INTEGER NOT NULL,
    agents       TEXT[] NOT NULL,
    status       TEXT NOT NULL DEFAULT 'running',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Agent SQL Changes

Every agent file that uses `NOW()` in a SQL string gets a single search-and-replace:

`NOW()` → `now_or_backtest()`

Affected files (13 total):
- `agents/technical/agent.py`
- `agents/sentiment/agent.py`
- `agents/macro/agent.py`
- `agents/research/agent.py`
- `agents/aggregator/agent.py`
- `agents/quant/momentum/agent.py`
- `agents/quant/mean_reversion/agent.py`
- `agents/quant/ml_quant/agent.py`
- `agents/quant/supervisor/agent.py`
- `agents/portfolio_mgr/agent.py`
- `agents/risk/checker.py`
- `agents/risk/agent.py`
- `agents/cio/agent.py`

No agent logic changes. No agent test changes (tests mock `db.fetch`, so the SQL string change is invisible to tests).

---

## New Dependencies

- `plotly` — chart generation (HTML/JS, self-contained)
- `jinja2` — HTML report templating

---

## Testing

| File | What it tests |
|------|--------------|
| `tests/backtest/test_clock.py` | tick count, step accuracy, start/end boundary |
| `tests/backtest/test_bus.py` | set/get round-trip, TTL ignored gracefully, subscribe yields nothing |
| `tests/backtest/test_db.py` | set_tick sets session variable, search_path set correctly |
| `tests/backtest/test_runner.py` | agent tiers fire in correct order, portfolio_state seeded at tick 0 |
| `tests/backtest/test_metrics.py` | Sharpe, drawdown, CAGR computed correctly from known fixture data |
| `tests/backtest/test_report.py` | HTML output contains expected metric values and chart markers |

---

## Data Flow Summary

```
prices / news / macro (public schema, read-only)
        ↓
BacktestClock → tick
        ↓
BacktestDB.set_tick(tick)  [SET LOCAL backtest.now = tick]
        ↓
Agent tiers 1-7 run_once() via BacktestDB + InMemoryBus
        ↓
signals / trades / positions / portfolio_state → bt_{run_id} schema
        ↓
ReportGenerator reads bt_{run_id} → metrics + HTML report
```
