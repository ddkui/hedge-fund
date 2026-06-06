# Self-Improving Agents — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Build order:** 5 of 5

---

## Overview

A closed-loop reinforcement system that tracks signal accuracy, adjusts agent parameters based on trade outcomes, detects market regimes, maintains separate parameter sets per regime, and monitors Jensen's Alpha against SPY. Small parameter adjustments happen automatically; large changes require CIO approval via the dashboard. Three alpha tiers govern how aggressively the system continues learning. The current regime and all parameter states are visible in a new "Intelligence" dashboard tab.

---

## Architecture

```
signal emitted → trade executed → trade closes → outcome recorded
                                                        ↓
                                            SignalOutcomeTracker
                                            links signal → PnL
                                                        ↓
                                            AgentOptimizer (24h cycle)
                                            ┌───────────────────────────┐
                                            │ compute signal accuracy    │
                                            │ per agent per regime       │
                                            │ adjust regime params       │
                                            │ small Δ → auto-apply       │
                                            │ large Δ → CIO proposal     │
                                            └───────────────────────────┘
                                                        ↓
                                            AlphaMonitor (daily)
                                            compute beta, Jensen's alpha
                                            classify tier → act
```

---

## Component 1 — Signal Outcome Tracker

### New DB table: `signal_outcomes`

```sql
CREATE TABLE IF NOT EXISTS signal_outcomes (
    id              BIGSERIAL PRIMARY KEY,
    time            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_id       BIGINT,
    agent           TEXT NOT NULL,
    symbol          TEXT,
    signal_type     TEXT NOT NULL,
    confidence      DOUBLE PRECISION,
    regime          TEXT NOT NULL,         -- macro regime at signal time
    entry_price     DOUBLE PRECISION,
    exit_price      DOUBLE PRECISION,
    pnl             DOUBLE PRECISION,
    was_correct     BOOLEAN,               -- predicted direction matched outcome
    horizon_candles INTEGER
);
SELECT create_hypertable('signal_outcomes', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS signal_outcomes_agent_regime ON signal_outcomes(agent, regime, time DESC);
```

### Linking mechanism

After each trade closes (status → `executed` and position exits), the `AgentOptimizer` runs a SQL join to find which signals contributed to that trade and records outcomes. A signal is "correct" if its direction matches the trade's PnL sign.

---

## Component 2 — Agent Parameters (`agent_params.yaml`)

All tunable parameters stored in `agent_params.yaml` at the repo root. The `AgentOptimizer` reads and writes this file. Each agent reads its own section on startup and after each optimizer cycle.

```yaml
# agent_params.yaml — auto-managed by AgentOptimizer
# DO NOT edit manually while agents are running

_meta:
  last_updated: "2026-06-06T14:00:00Z"
  optimizer_version: 1
  alpha_tier: learning            # learning | alpha_achieved | exceptional_alpha

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
  stagflation: *nm_default
  hiking_cycle: *nm_default
  cutting_cycle: *nm_default
  pandemic:
    sentiment_weight: 0.80
    momentum_weight: 0.20
    composite_threshold: 4.0
    momentum_lookback: 5
    sentiment_lookback_hours: 1

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

technical:
  _default: &tech_default
    rsi_oversold: 30
    rsi_overbought: 70
    macd_signal_threshold: 0.0
  expansion: *tech_default
  contraction:
    rsi_oversold: 40
    rsi_overbought: 60
    macd_signal_threshold: 0.5
  crisis:
    rsi_oversold: 50
    rsi_overbought: 50
    macd_signal_threshold: 1.0
  pandemic:
    rsi_oversold: 55
    rsi_overbought: 45
    macd_signal_threshold: 2.0
  stagflation: *tech_default
  hiking_cycle: *tech_default
  cutting_cycle: *tech_default

aggregator:
  _default: &agg_default
    agent_weights:
      technical: 1.0
      sentiment: 1.0
      macro: 1.0
      research: 1.0
      news_momentum: 1.0
      vwap: 1.0
      kronos: 1.0
  expansion: *agg_default
  contraction:
    agent_weights:
      technical: 0.8
      sentiment: 1.2
      macro: 1.5
      research: 1.0
      news_momentum: 1.2
      vwap: 0.6
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

### Regime inheritance

If a regime has no learned parameters (e.g. first time in `crisis`), the optimizer inherits from the closest regime by volatility similarity:
```
pandemic → crisis → contraction → expansion → cutting_cycle → hiking_cycle → stagflation
```

Historical data is used to pre-warm regime parameters on first deployment: backtesting the `prices` table against known regime periods (2020 March = crisis/pandemic, 2022 = hiking_cycle, etc.).

---

## Component 3 — Regime Detection (extended macro agent)

The macro agent already emits regimes. Two new regimes are added:

| Regime | Detection criteria |
|--------|-------------------|
| `crisis` | VIX proxy > 30 (inferred from SPY daily moves > 3%), macro agent signals contraction with confidence > 80% |
| `pandemic` | crisis conditions + news sentiment bulk negative across >80% of symbols + unusual cross-asset correlation (stocks + crypto falling together) |

The detected regime is stored in Redis key `macro:current_regime` and read by every agent on each `run_once()` cycle to load the correct parameter set.

---

## Component 4 — Agent Optimizer (`agents/optimizer/agent.py`)

New agent. Runs every 24 hours.

### Per-agent accuracy computation

```python
for each agent in [technical, sentiment, news_momentum, vwap, kronos, aggregator]:
    for each regime in active_regimes_last_30d:
        accuracy = count(was_correct=True) / count(*) from signal_outcomes
        avg_pnl  = avg(pnl) from signal_outcomes
        # accuracy below 45% or avg_pnl negative = needs adjustment
```

### Parameter adjustment rules

**Small adjustment (≤10% change) → auto-apply:**
- If news_momentum accuracy in `contraction` regime < 48%: reduce `composite_threshold` by 5%
- If vwap accuracy in any regime < 45%: increase `deviation_threshold_pct` by 0.1
- If an agent's weight in aggregator correlates with loss: reduce weight by 0.05
- All changes written to `agent_params.yaml`, logged to `optimizer_history` table

**Large adjustment (>10% change) → CIO proposal:**
- Publish to Redis `optimizer.proposal` channel
- Written to `optimizer_proposals` DB table with status=`pending`
- Appears in dashboard "Intelligence" tab as pending proposal with Approve/Reject buttons
- CIO agent sees pending proposals in its context and can approve via chat

### New DB tables

```sql
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
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending|approved|rejected
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
    auto_applied    BOOLEAN
);
SELECT create_hypertable('optimizer_history', 'time', if_not_exists => TRUE);
```

---

## Component 5 — Alpha Monitor (`agents/optimizer/alpha_monitor.py`)

Runs daily. Computes beta, Jensen's Alpha, and Sharpe against SPY.

### Beta and Jensen's Alpha computation

```python
# Fetch last 30 days of daily returns
portfolio_returns = daily_pct_change(portfolio_state.total_value, 30d)
spy_returns       = daily_pct_change(prices WHERE symbol='SPY', 30d)

# Beta = covariance(portfolio, SPY) / variance(SPY)
beta = cov(portfolio_returns, spy_returns) / var(spy_returns)

# Annualised returns
portfolio_annual = (1 + mean(portfolio_returns)) ** 252 - 1
spy_annual       = (1 + mean(spy_returns)) ** 252 - 1

# Jensen's Alpha = portfolio_return - (beta × SPY_return)
jensens_alpha = portfolio_annual - (beta * spy_annual)

# Rolling Sharpe
sharpe = mean(portfolio_returns) / std(portfolio_returns) * sqrt(252)
```

### Alpha tier classification

| Tier | Condition | Learning rate | Action |
|------|-----------|--------------|--------|
| `learning` | Jensen's Alpha < 2% OR Sharpe < 1.5 | Full (100%) | Optimizer runs unrestricted |
| `alpha_achieved` | Sharpe ≥ 1.5 AND Jensen's Alpha ≥ 2% | Micro (10%) | Lock params, micro-adjustments only, email alert "Alpha achieved" |
| `exceptional_alpha` | Sharpe ≥ 2.0 AND Jensen's Alpha ≥ 5% | Frozen (0%) | Full lock, email alert "Exceptional alpha", write named strategy to Obsidian |

**Exceptional alpha — named strategy preservation:**
When exceptional alpha is reached, the current `agent_params.yaml` is snapshotted and saved to `memory/obsidian/strategies/YYYY-MM-DD-exceptional-alpha.md` with full context: regime, parameters, beta, Sharpe, Jensen's Alpha, date range. This preserves the winning configuration for replay.

**Alpha erosion — unlock:**
```python
if tier == 'alpha_achieved' and (sharpe < 1.2 or jensens_alpha < 0.0):
    → downgrade to 'learning'
    → email alert "Alpha eroded, resuming optimization"

if tier == 'exceptional_alpha' and (sharpe < 1.5 or jensens_alpha < 2.0):
    → downgrade to 'alpha_achieved'
    → email alert "Exceptional alpha eroded"
```

Beta, Jensen's Alpha, Sharpe, and tier stored in Redis `alpha:status` key for real-time dashboard access.

---

## Component 6 — Dashboard Intelligence Tab (`/intelligence`)

New dashboard page visible in the sidebar as "Intelligence" with a `Brain` icon.

### Layout

```
┌─────────────────────────────────────────────────────────────┐
│  INTELLIGENCE — Self-Improving Agent System                  │
├─────────────────────────────────────────────────────────────┤
│  ALPHA STATUS                                                │
│  ┌──────────────┬──────────────┬──────────────┬───────────┐ │
│  │ Tier         │ Sharpe (30d) │ Jensen Alpha │ Beta      │ │
│  │ LEARNING     │ 0.87         │ +1.2%        │ 0.94      │ │
│  └──────────────┴──────────────┴──────────────┴───────────┘ │
│  [progress bar toward alpha_achieved thresholds]            │
├─────────────────────────────────────────────────────────────┤
│  CURRENT REGIME                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  EXPANSION  (detected 3 days ago)                     │  │
│  │  Regime history: expansion → contraction → expansion  │  │
│  └───────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  AGENT ACCURACY (this regime, last 30d)                     │
│  Agent          │ Correct │ Avg PnL │ Signals │ Weight     │
│  technical      │ 58%     │ +$42    │ 241     │ 1.0        │
│  news_momentum  │ 61%     │ +$67    │ 183     │ 1.1 ↑      │
│  vwap           │ 47%     │ -$12    │ 156     │ 0.9 ↓      │
│  kronos         │ 53%     │ +$28    │  88     │ 1.0        │
├─────────────────────────────────────────────────────────────┤
│  REGIME PARAMETER SETS  [expansion ▼] (dropdown selector)  │
│  news_momentum: threshold=1.0, sentiment_w=0.40 …          │
│  vwap: deviation=1.5%, min_candles=5 …                     │
│  technical: RSI 30/70 …                                     │
├─────────────────────────────────────────────────────────────┤
│  PENDING PROPOSALS  (requires CIO approval)                 │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ news_momentum › contraction › composite_threshold    │   │
│  │ 2.00 → 2.80 (+40%)  Reason: accuracy 38% last 7d   │   │
│  │ [✓ Approve]  [✗ Reject]                              │   │
│  └──────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  PARAMETER CHANGE HISTORY  (last 7d)                        │
│  2026-06-05  vwap › crisis › deviation_threshold 1.5→1.65  │
│  2026-06-04  aggregator › expansion › kronos weight 1.0→1.1 │
│  …                                                          │
├─────────────────────────────────────────────────────────────┤
│  NAMED STRATEGIES (exceptional alpha snapshots)             │
│  No exceptional alpha achieved yet.                         │
└─────────────────────────────────────────────────────────────┘
```

### Real-time updates

- Alpha status card polls `GET /intelligence/status` every 30s
- Regime indicator polls every 60s
- Pending proposals use SWR with 10s refresh
- When a proposal is approved/rejected, POST to `gateway /intelligence/proposals/{id}/approve|reject`

### Gateway endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /intelligence/status` | Alpha tier, Sharpe, Jensen's Alpha, beta, current regime |
| `GET /intelligence/accuracy` | Per-agent accuracy + weights for current regime |
| `GET /intelligence/params?regime=expansion` | Current parameter set for a regime |
| `GET /intelligence/proposals` | Pending CIO approval proposals |
| `POST /intelligence/proposals/{id}/approve` | Approve a parameter change |
| `POST /intelligence/proposals/{id}/reject` | Reject a parameter change |
| `GET /intelligence/history` | Last 50 parameter change history entries |
| `GET /intelligence/strategies` | Named exceptional-alpha strategy snapshots |

---

## Files

### New
- `agents/optimizer/__init__.py`
- `agents/optimizer/agent.py` — `AgentOptimizer`
- `agents/optimizer/alpha_monitor.py` — `AlphaMonitor`
- `agents/optimizer/main.py`
- `agent_params.yaml`
- `gateway/routers/intelligence.py`
- `dashboard/app/intelligence/page.tsx`
- `dashboard/components/intelligence/alpha-status.tsx`
- `dashboard/components/intelligence/regime-card.tsx`
- `dashboard/components/intelligence/accuracy-table.tsx`
- `dashboard/components/intelligence/params-view.tsx`
- `dashboard/components/intelligence/proposals-list.tsx`
- `dashboard/components/intelligence/history-log.tsx`
- `dashboard/components/intelligence/strategies-list.tsx`
- `tests/agents/optimizer/test_optimizer.py`
- `tests/agents/optimizer/test_alpha_monitor.py`
- `tests/gateway/test_intelligence.py`

### Modified
- `agents/macro/agent.py` — add crisis/pandemic regime detection
- `agents/aggregator/agent.py` — read agent weights from agent_params.yaml per regime
- `agents/technical/agent.py` — read RSI thresholds from agent_params.yaml per regime
- `agents/quant/news_momentum/agent.py` — read params from agent_params.yaml per regime
- `agents/quant/vwap/agent.py` — read params from agent_params.yaml per regime
- `scripts/setup_db.py` — add signal_outcomes, optimizer_proposals, optimizer_history tables
- `scripts/start_all.py` — add optimizer agent
- `dashboard/components/layout/sidebar.tsx` — add Intelligence nav entry
- `gateway/main.py` — register intelligence router

---

## Tests

### Optimizer
- `test_optimizer_computes_accuracy_per_regime` — mock signal_outcomes, assert correct accuracy
- `test_small_change_auto_applied` — Δ ≤ 10%, assert yaml updated, no proposal created
- `test_large_change_creates_proposal` — Δ > 10%, assert proposal written to DB
- `test_regime_inheritance_on_unknown_regime` — no params for regime, assert inherits from closest
- `test_params_load_from_yaml_on_startup` — assert agent reads correct regime params

### Alpha Monitor
- `test_beta_computation_correct` — known portfolio + SPY returns, assert beta formula
- `test_jensens_alpha_correct` — assert alpha = portfolio_return - (beta × spy_return)
- `test_tier_transition_learning_to_alpha` — Sharpe ≥ 1.5 + alpha ≥ 2%, assert tier change + email
- `test_tier_transition_to_exceptional` — Sharpe ≥ 2.0 + alpha ≥ 5%, assert strategy saved to Obsidian
- `test_alpha_erosion_unlocks_optimizer` — tier drops back, assert learning resumes
- `test_exceptional_alpha_snapshot_written` — assert Obsidian file created with correct content
