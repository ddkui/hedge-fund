# Phase 4 — Portfolio & Execution Layer Design

**Date:** 2026-05-23
**Status:** Approved

---

## Goal

Build the 9 agents that convert AI + quant signals into actual (paper or live) trades: a quant signal layer (momentum, mean reversion, ML ensemble, supervisor), a portfolio manager with Kelly sizing, a risk manager with full guardrails, an execution agent with Alpaca/Binance integration, a CIO agent that dialogues with the PM, and an ops agent that monitors system health.

---

## Architecture

### Data Flow

```
[Phase 3: aggregator]  →  consensus signals (DB signals table + Redis)
        |
        |  CIO checks Redis cio:directive:{symbol} flags each cycle
        ↓
[Quant Supervisor]     →  weighted quant consensus signal per symbol
        |
        ↓
[Portfolio Manager]    →  reads aggregator + quant_supervisor signals
                           re-analyzes CIO directives independently
                           Kelly sizing + synchronous risk validation
                           writes pending trade → trades table
        |
        ↓  (5s poll)
[Execution Agent]      →  paper: simulate fill from latest price
                           live: Alpaca (stocks) or Binance (crypto)
        |
        ↓
[Risk Agent]           →  2min poll, monitors positions, force-closes breaches
[CIO Agent]            →  1hr poll, LLM review, Redis directives, PM dialogue
[Ops Agent]            →  heartbeat subscription, agent_health writes, Gmail alerts
```

### Approach: Hybrid poll + fast execution

- All agents use the existing `BaseAgent` poll-based pattern
- Exception: execution agent polls every 5s (not `interval_seconds`)
- Exception: ops agent subscribes to `ops.heartbeat` Redis channel continuously
- CIO–PM communication via Redis directive keys (25h TTL)
- Risk validation runs synchronously inside the PM before writing any trade

---

## New DB Tables

```sql
CREATE TABLE IF NOT EXISTS portfolio_state (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cash         DOUBLE PRECISION NOT NULL,
    total_value  DOUBLE PRECISION NOT NULL,
    peak_value   DOUBLE PRECISION NOT NULL,
    open_positions INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS risk_events (
    id           SERIAL PRIMARY KEY,
    time         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    agent        TEXT NOT NULL,
    symbol       TEXT,
    limit_type   TEXT NOT NULL,   -- 'position_size' | 'drawdown' | 'var' | 'correlation' | 'open_positions'
    details      TEXT NOT NULL,
    action_taken TEXT NOT NULL    -- 'trade_rejected' | 'position_force_closed'
);
```

### Existing tables used by Phase 4

- `signals` — read by PM and CIO; written by all quant agents, PM (`cio_override`), CIO (`daily_brief`)
- `positions` — read/written by PM and execution agent
- `trades` — written by PM and risk agent; read/executed by execution agent
- `quant_algos` — written by quant supervisor (performance tracking)
- `agent_health` — written by ops agent

---

## New Config Keys

Added to `shared/config.py` with these defaults (all overridable via `.env`):

```python
kelly_multiplier: float = 0.25          # fractional Kelly dampener
risk_max_position_pct: float = 0.10     # max 10% per symbol
risk_max_positions: int = 10            # max open positions
risk_max_drawdown_pct: float = 0.20     # max 20% drawdown from peak
risk_var_limit_pct: float = 0.05        # daily VaR 95% limit: 5% of portfolio
risk_max_correlated: int = 3            # max symbols with pairwise corr > 0.7
initial_capital: float = 100_000.0      # starting paper portfolio value
alpaca_base_url: str = "https://paper-api.alpaca.markets"  # paper by default
binance_base_url: str = "https://api.binance.com"
```

---

## New Packages

```
scikit-learn==1.5.0        # ML ensemble (LogisticRegression, RF, GBM)
alpaca-py==0.20.0          # Alpaca REST API for live stock orders
python-binance==1.0.19     # Binance REST API for live crypto orders
```

Only `scikit-learn` is used in paper mode. Broker SDKs are only invoked when `paper_trading=False`.

---

## Agent Designs

### 1. MomentumQuantAgent (`agents/quant/momentum/`)

- **Interval:** 2 minutes
- **Extends:** `AnalysisAgent`
- **Logic:** Computes price momentum over 5, 20, and 60 bars from `prices` table. Signal is bullish when momentum is positive and accelerating across all three timeframes, bearish when negative and decelerating. Confidence scales with alignment strength (1 timeframe = 40, 2 = 65, 3 = 85).
- **Output:** `store_signal(signal_type='momentum_bullish'|'momentum_bearish'|'momentum_neutral', ...)`
- **Quant algo tracking:** Registers in `quant_algos` table on first run with `strategy_type='momentum'`.

### 2. MeanReversionQuantAgent (`agents/quant/mean_reversion/`)

- **Interval:** 2 minutes
- **Extends:** `AnalysisAgent`
- **Logic:** Z-score of price vs 20-bar rolling mean. Signal fires when |Z| > 2.0. RSI confirmation required (RSI < 35 for bullish reversion, RSI > 65 for bearish). Confidence = min(100, |Z| * 35).
- **Output:** `store_signal(signal_type='reversion_bullish'|'reversion_bearish', ...)`

### 3. MLQuantAgent (`agents/quant/ml_quant/`)

- **Interval:** 2 minutes (inference); 24h (retrain)
- **Extends:** `AnalysisAgent`
- **Features (per symbol, from DB):** RSI, MACD histogram, BB%, ATR, OBV trend (5-bar diff), 1/5/20-bar price momentum, volume ratio (current vs 20-bar avg) — 10 features total.
- **Labels:** +1 if close up >0.5% next bar, -1 if down >0.5%, 0 otherwise.
- **Ensemble:** `LogisticRegression` + `RandomForestClassifier` + `GradientBoostingClassifier`. Majority vote → direction. Average predicted probability → confidence.
- **Training data:** Last 30 days of 1-min OHLCV from `prices` table. Minimum 500 bars required to train; skips symbol if insufficient data.
- **Retrain schedule:** Tracks last train time per symbol in memory; retrains if >24h elapsed.
- **Output:** `store_signal(signal_type='ml_bullish'|'ml_bearish'|'ml_neutral', confidence=avg_prob*100, metadata={'votes': {...}, 'feature_importance': {...}})`

### 4. QuantSupervisorAgent (`agents/quant/supervisor/`)

- **Interval:** 5 minutes
- **Extends:** `AnalysisAgent`
- **Logic:** Reads last 10 minutes of signals from `momentum`, `mean_reversion`, `ml_quant` agents. Weights each by its algo's Sharpe ratio from `quant_algos` (default weight 1.0 for new algos). Computes weighted directional score per symbol → consensus.
- **Algo performance updates:** After each trade closes (reads `trades` where `status='executed'`), computes return and updates `quant_algos` (rolling Sharpe, win rate, trade count, max drawdown).
- **Retirement:** Retires algos with Sharpe < 0 after ≥ 20 trades. Sets `status='retired'`, `retired_at=NOW()`, `retirement_reason='sharpe_negative'`.
- **Output:** `store_signal(agent='quant_supervisor', signal_type='quant_bullish'|'quant_bearish'|'quant_neutral', ...)`

---

### 5. PortfolioManagerAgent (`agents/portfolio_mgr/`)

- **Interval:** 2 minutes
- **Extends:** `AnalysisAgent`

#### Signal intake

Reads last 10 minutes of signals from `aggregator` (weight 0.60) and `quant_supervisor` (weight 0.40). For each symbol, computes:

```python
combined_confidence = (
    aggregator_confidence * 0.60 +
    quant_confidence * 0.40
)
combined_direction = aggregator_direction  # aggregator is primary
```

#### CIO directive check

Before any decision, checks Redis for `cio:directive:{symbol}`. Three cases:

- `low_conviction`: multiplies `combined_confidence` by `directive["confidence_multiplier"]`
- `avoid_open`: skips opening new positions for that symbol — but if combined_confidence > 85, PM overrides, logs `cio_override` signal with reasoning
- `request_close`: triggers **re-analysis** (see below)

#### CIO request_close re-analysis

1. Fetches fresh signals for the symbol (last 5 minutes)
2. Re-runs scoring with fresh data
3. Decision:
   - Signals weak/bearish → agrees, writes close trade, logs `"CIO request confirmed"`
   - Signals still strong (confidence > 70) → overrides, keeps position, logs `cio_override` signal
   - Signals mixed (40–70) → applies `low_conviction` multiplier 0.5, monitors next cycle

#### Kelly position sizing

```python
kelly_fraction = (combined_confidence / 100) * settings.kelly_multiplier
position_value = portfolio_value * kelly_fraction
position_value = clamp(position_value,
    min=portfolio_value * 0.005,   # 0.5% minimum
    max=portfolio_value * settings.risk_max_position_pct
)
quantity = position_value / current_price
```

#### Decision logic

| Signal | Existing position | Action |
|--------|------------------|--------|
| `consensus_bullish` | None | Open LONG |
| `consensus_bearish` | None | Open SHORT (stocks only) |
| `consensus_neutral` | Open | Close position |
| `consensus_bullish` | Long already | Skip (no pyramiding) |
| `consensus_bearish` | Short already | Skip |

Crypto (`USDT`-suffix symbols) is long-only — no short positions opened.

#### Synchronous risk validation

Calls `RiskChecker.validate(symbol, direction, quantity, price)` before writing any trade. If rejected, logs to `risk_events` and skips. See Risk Agent for limits.

#### Trade write

On approval: inserts into `trades` with `status='pending'`, `paper=settings.paper_trading`, `pm_reasoning=<reasoning string>`, `confidence=combined_confidence`.

---

### 6. RiskAgent (`agents/risk/`)

- **Interval:** 2 minutes
- **Extends:** `BaseAgent`

#### RiskChecker (shared module: `agents/risk/checker.py`)

Plain Python class, imported by `PortfolioManagerAgent`. Validates a proposed trade against all limits:

| Limit | Check |
|-------|-------|
| Position size | `position_value / portfolio_value <= risk_max_position_pct` |
| Open positions | `open_position_count < risk_max_positions` |
| Drawdown | `(peak_value - current_value) / peak_value < risk_max_drawdown_pct` |
| Daily VaR (95%) | Portfolio VaR from 30-day returns < `risk_var_limit_pct * portfolio_value` |
| Correlation | Adding symbol would not create 4th in a cluster with pairwise corr > 0.7 |

**VaR calculation:** Historical simulation on last 30 days of daily `close` prices for all open positions. Computes daily portfolio return distribution → 5th percentile → VaR. Result cached in Redis for 5 minutes (`risk:var_cache`).

**Correlation check:** Fetches 20-day daily return series for all open symbols + proposed symbol. Computes pairwise Pearson correlation matrix. Rejects if proposed symbol has corr > 0.7 with ≥ `risk_max_correlated` existing positions.

#### RiskAgent (running monitor)

Each cycle:
1. Reads all open positions and current prices
2. Re-runs all limit checks against current portfolio state
3. If drawdown limit breached: writes `pending` close trade for the largest losing position to `trades` table (force-close path)
4. Logs all breaches to `risk_events`

---

### 7. ExecutionAgent (`agents/execution/`)

- **Interval:** 5 seconds
- **Extends:** `BaseAgent`

#### Poll loop

Fetches `trades WHERE status = 'pending'` ordered by `time ASC`. Processes each in a DB transaction:

1. Fetch latest price for symbol
2. Attempt fill (paper or live)
3. Update trade: `status='executed'`, `price=fill_price`
4. Update position: insert (open) or update `exit_price/exit_time/status='closed'` (close)
5. Update `portfolio_state`: cash ± (quantity × fill_price)
6. Update `peak_value` if `total_value > peak_value`

All steps within a single `asyncpg` transaction — crash-safe.

#### Paper mode

Fill price = latest `close` from `prices` table for that symbol. Simulates immediate market fill.

#### Live mode (`paper_trading=False`)

- **Stocks** (no `USDT` suffix): Alpaca REST API via `alpaca-py`. Market order. Reads fill price from order response.
- **Crypto** (`USDT` suffix): Binance REST API via `python-binance`. Market order.
- **Error handling:** One retry after 2s. On second failure: `status='failed'`, log to `risk_events`.

---

### 8. CIOAgent (`agents/cio/`)

- **Interval:** 1 hour
- **Extends:** `AnalysisAgent`

#### Data intake (each cycle)

- Last 24h signals from all agents
- All open positions with unrealized P&L (computed from latest prices)
- Last 7 days of closed trades with realized P&L
- Latest macro regime signal
- Last 24h `risk_events`
- Last 24h `cio_override` signals from PM (so CIO sees when PM pushed back)

#### LLM review

Sends structured prompt to Ollama (research model). Asks for a JSON list of per-symbol directives:

```json
[
  {
    "symbol": "AAPL",
    "action": "low_conviction" | "avoid_open" | "request_close" | "none",
    "confidence_multiplier": 0.0–1.0,
    "reason": "one sentence"
  }
]
```

#### Directive publishing

For each non-`none` directive: sets Redis key `cio:directive:{symbol}` with 25h TTL. PM reads on next cycle.

If PM previously overrode a `request_close` (visible in `cio_override` signals), CIO notes this in its daily brief but does not re-escalate — PM's independent judgment is respected.

#### Daily brief

Writes to `signals` table: `agent='cio'`, `signal_type='daily_brief'`, `symbol=None`, full LLM narrative in `reasoning`, structured metadata with positions summary, P&L, active directives.

---

### 9. OpsAgent (`agents/ops/`)

- **Extends:** `BaseAgent`
- **Mode:** Subscribes to `ops.heartbeat` Redis channel continuously; also runs a 60s check loop

#### Heartbeat tracking

Maintains `{agent_name: last_seen: datetime}` in memory. Populated from `start_all.py` AGENTS list at startup (known agents).

Silence thresholds (based on each agent's `interval_seconds`):
- `> 2 × interval_seconds` → `status='degraded'`
- `> 5 × interval_seconds` → `status='down'`

#### agent_health writes

On each heartbeat received: upserts `agent_health` row (`status='healthy'`).
On degraded/down detection: writes `status='degraded'|'down'` with gap duration in metadata.

#### Gmail alerts

On `status='down'`: sends email via `smtplib` (no new dependency). Rate-limited to one email per agent per hour. Uses `gmail_sender` from config as both sender and recipient.

---

## File Map

| File | Action |
|------|--------|
| `agents/quant/__init__.py` | Create |
| `agents/quant/momentum/__init__.py` | Create |
| `agents/quant/momentum/agent.py` | Create |
| `agents/quant/momentum/main.py` | Create |
| `agents/quant/mean_reversion/__init__.py` | Create |
| `agents/quant/mean_reversion/agent.py` | Create |
| `agents/quant/mean_reversion/main.py` | Create |
| `agents/quant/ml_quant/__init__.py` | Create |
| `agents/quant/ml_quant/agent.py` | Create |
| `agents/quant/ml_quant/main.py` | Create |
| `agents/quant/supervisor/__init__.py` | Create |
| `agents/quant/supervisor/agent.py` | Create |
| `agents/quant/supervisor/main.py` | Create |
| `agents/portfolio_mgr/__init__.py` | Create |
| `agents/portfolio_mgr/agent.py` | Create |
| `agents/portfolio_mgr/main.py` | Create |
| `agents/risk/__init__.py` | Create |
| `agents/risk/checker.py` | Create |
| `agents/risk/agent.py` | Create |
| `agents/risk/main.py` | Create |
| `agents/execution/__init__.py` | Create |
| `agents/execution/agent.py` | Create |
| `agents/execution/main.py` | Create |
| `agents/cio/__init__.py` | Create |
| `agents/cio/agent.py` | Create |
| `agents/cio/main.py` | Create |
| `agents/ops/__init__.py` | Create |
| `agents/ops/agent.py` | Create |
| `agents/ops/main.py` | Create |
| `shared/config.py` | Modify — add 9 new config keys |
| `scripts/setup_db.py` | Modify — add portfolio_state and risk_events tables |
| `scripts/start_all.py` | Modify — uncomment all Phase 4 agents |
| `requirements.txt` | Modify — add scikit-learn, alpaca-py, python-binance |
| `tests/agents/quant/momentum/test_agent.py` | Create |
| `tests/agents/quant/mean_reversion/test_agent.py` | Create |
| `tests/agents/quant/ml_quant/test_agent.py` | Create |
| `tests/agents/quant/supervisor/test_agent.py` | Create |
| `tests/agents/portfolio_mgr/test_agent.py` | Create |
| `tests/agents/risk/test_checker.py` | Create |
| `tests/agents/risk/test_agent.py` | Create |
| `tests/agents/execution/test_agent.py` | Create |
| `tests/agents/cio/test_agent.py` | Create |
| `tests/agents/ops/test_agent.py` | Create |

---

## PM–CIO Dialogue Summary

```
CIO sets directive → PM reads on next cycle → PM re-analyzes independently
    → agrees: executes, logs "CIO request confirmed"
    → disagrees: overrides, logs cio_override signal with reasoning
    → mixed: applies low_conviction multiplier, re-evaluates next cycle

CIO reads cio_override on next hourly cycle → notes PM pushback in daily brief
    → does NOT re-escalate (PM judgment respected)
```

---

## Spec Self-Review

- **No placeholders:** All agent behaviors, data flows, and DB interactions fully specified.
- **Internal consistency:** `RiskChecker` imported by PM; `RiskAgent` instantiates its own copy — no circular import. PM owns all trade writes except force-close path (Risk Agent). CIO only writes directives to Redis and records to `signals`.
- **Scope:** Large but coherent — all 9 agents form one trading pipeline. Decomposing further would leave subsystems half-functional.
- **Ambiguity resolved:** Crypto is long-only. No pyramiding. CIO cannot hard-block — PM has final say. Force-close path closes largest losing position (not all positions) on drawdown breach.
