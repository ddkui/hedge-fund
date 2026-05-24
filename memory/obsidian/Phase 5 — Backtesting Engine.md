# Phase 5 — Backtesting Engine

**Date:** 2026-05-23 → 2026-05-24  
**Repo:** github.com/ddkui/hedge-fund  
**Branch:** master (pushed directly)  
**Commits:** `60b12bf` → `eb84d92` (13 commits)  
**Tests:** 187 passing

---

## What Was Built

A full backtesting engine that replays the existing agent pipeline against historical PostgreSQL data and produces an interactive HTML report with equity curve and trade log.

### Run it

```bash
python backtest/cli.py \
  --start 2024-01-01 \
  --end   2024-12-31 \
  --step  1h \
  --output reports/backtest_2024.html
```

---

## Architecture

**Time simulation:** PostgreSQL session variable `backtest.now`. A `now_or_backtest()` SQL function returns the session variable if set, else `NOW()`. Set via `SELECT set_config('backtest.now', $1, false)` on a single connection — so it persists across all agent queries in a tick.

**Schema isolation:** Each run gets a dedicated schema `bt_{run_id}`. `search_path = bt_{run_id}, public` — writes go to shadow tables, reads fall through to public (prices, news, macro).

**Single connection invariant:** `BacktestDB` uses one `asyncpg.Connection` (not a pool) because session variables are connection-scoped. A pool would lose the variable on each query.

**Python timestamp override:** `BaseAgent._now()` returns `datetime.now(timezone.utc)` by default. In backtest, runner sets `agent._now = lambda: db.current_tick` so Python-side inserts match the simulated tick.

**Tier execution (sequential, in order):**
1. `technical`, `sentiment`, `macro`, `research` (parallel by default — fired sequentially in backtest)
2. `aggregator`
3. `momentum`, `mean_reversion`, `ml_quant`
4. `quant_supervisor`
5. `portfolio_mgr`
6. `risk`
7. `execution`

Default agent set excludes LLM-heavy agents (technical, sentiment, macro, research) and cio/ops.

---

## Files Created / Modified

| File | What |
|---|---|
| `scripts/setup_backtest_db.py` | Creates `now_or_backtest()` + `backtest_runs` table |
| `scripts/setup_db.py` | Also includes `now_or_backtest()` for fresh setups |
| `shared/agent_base.py` | Added `_now()` method |
| `agents/base.py` | `store_signal` uses `self._now()` |
| `agents/portfolio_mgr/agent.py` | `_write_trade`, `_log_risk_event` use `self._now()` |
| `agents/execution/agent.py` | `_apply_fill`, `_fail_trade` use `self._now()` |
| `agents/risk/agent.py` | `_force_close_largest_loser`, `_log_event` use `self._now()` |
| `agents/quant/ml_quant/agent.py` | `_maybe_retrain` uses `self._now()` |
| `agents/ops/agent.py` | 5 call sites use `self._now()` |
| 13 agent SQL files | `NOW()` → `now_or_backtest()` |
| `backtest/__init__.py` | Package marker |
| `backtest/clock.py` | `BacktestClock` — tick iterator |
| `backtest/bus.py` | `InMemoryBus` — Redis drop-in |
| `backtest/db.py` | `BacktestDB` — single connection + schema isolation |
| `backtest/runner.py` | `BacktestRunner` — tiered execution, portfolio seed |
| `backtest/metrics.py` | `compute_metrics` — Sharpe, CAGR, drawdown, return |
| `backtest/report.py` | `ReportGenerator` — jinja2 + plotly HTML report |
| `backtest/templates/report.html.j2` | HTML template |
| `backtest/cli.py` | CLI entry point |
| `requirements.txt` | Added `plotly==5.22.0`, `jinja2==3.1.4` |

---

## Key Design Decisions

### `now_or_backtest()` vs modifying agent SQL
Chose a SQL function that transparently returns real or simulated time. Agents don't know they're backtesting — the same `run_once()` code runs in both modes.

### Single asyncpg connection
PostgreSQL session variables are scoped to a connection. A pool would assign different connections per query, dropping the variable. `BacktestDB` holds one connection for the entire run.

### `_now()` override pattern
`agent._now = lambda: db.current_tick` replaces the method at the instance level. No subclassing needed. Works for all BaseAgent subclasses.

### Shadow schema
`bt_{run_id}` schema is created at run start and dropped at end (unless `--keep-schema`). Agents write to shadow `signals`, `trades`, `positions`, `portfolio_state`, `risk_events`, `agent_health` — public tables are never touched.

### Failure handling
`_main` uses try/finally — on any failure, schema is dropped and `backtest_runs.status` is set to `'failed'` (not left stuck at `'running'`).

---

## Tests Added

| Test file | What it covers |
|---|---|
| `tests/backtest/test_infrastructure.py` | `now_or_backtest()` + `backtest_runs` DDL |
| `tests/backtest/test_now_refactor.py` | `_now()` default, override, flows into `store_signal` |
| `tests/backtest/test_sql_now.py` | No raw `NOW()` in any of 13 agent files (regression guard) |
| `tests/backtest/test_clock.py` | Tick count, step accuracy, boundary inclusion |
| `tests/backtest/test_bus.py` | set/get roundtrip, TTL ignored, subscribe yields nothing |
| `tests/backtest/test_db.py` | search_path, set_tick session variable, shadow table DDL |
| `tests/backtest/test_runner.py` | Tick ordering, portfolio seed, agent error isolation |
| `tests/backtest/test_metrics.py` | Sharpe=0 for flat, drawdown 25%, CAGR 1yr |
| `tests/backtest/test_report.py` | HTML output, plotly present, metric values rendered |
| `tests/backtest/test_cli.py` | Step parsing, date parsing, default agents |

---

## Issues Fixed During Review

1. **Test patch namespace** — `asyncpg.connect` patched as `scripts.setup_backtest_db.asyncpg.connect` with `importlib.reload()` for cache safety
2. **Missed `_now()` call sites** — `ml_quant/agent.py` (1) and `ops/agent.py` (5) caught by final code review
3. **`SET backtest.now` string interpolation** → replaced with `SELECT set_config('backtest.now', $1, false)` (parameterized)
4. **`agent_health` not in shadow schema** → added defensively so ops agent can't accidentally write to live table
5. **No failure handling in `_main`** → wrapped in try/finally, sets `status='failed'` and drops schema on any exception

---

## Spec & Plan

- Spec: `docs/superpowers/specs/2026-05-23-phase-5-backtesting-design.md`
- Plan: `docs/superpowers/plans/2026-05-23-phase-5-backtesting-engine.md`

---

## Tags

#hedge-fund #backtesting #phase-5 #python #postgresql
