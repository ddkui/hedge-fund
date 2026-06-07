# AI Hedge Fund

An autonomous AI-powered hedge fund that trades across multiple brokers simultaneously, analyzes market sentiment, executes quant strategies, and self-improves through alpha monitoring.

**Status:** 335 tests passing | Production-ready for paper & live trading | Multi-broker copy-trading enabled

---

## System Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         MARKET DATA INGESTION                        │
├─────────────────────────────────────────────────────────────────────┤
│  yfinance (stocks) → TimescaleDB ← Capital.com (forex/commodities)  │
│  Binance WebSocket (crypto) → OHLCV tables                         │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
        ┌──────────────────┴──────────────────┐
        │                                     │
┌───────▼────────────────┐       ┌───────────▼──────────────┐
│   ANALYSIS AGENTS      │       │   SIGNAL GENERATION      │
├────────────────────────┤       ├────────────────────────────┤
│ • Technical (MACD)     │       │ • News-Momentum Agent     │
│ • Sentiment (NLP)      │       │ • VWAP Deviation Agent    │
│ • Macro (Fed data)     │       │ • Supply-Demand Zones     │
│ • Research (LLM)       │       │ • Momentum/Mean-Reversion │
│ • Aggregator (weighted)│       │ • ML Quant / Kronos AI    │
└────────────┬───────────┘       └───────────┬───────────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                    ┌────────▼────────┐
                    │  AGGREGATOR:    │
                    │ Consensus Score │
                    │ (weighted avg)  │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
┌───────▼───────┐  ┌────────▼────────┐  ┌───────▼────────┐
│ PORTFOLIO MGR │  │   RISK AGENT    │  │  CIO (Advisor) │
├───────────────┤  ├─────────────────┤  ├────────────────┤
│ • Position    │  │ • Drawdown      │  │ • Veto power   │
│   sizing      │  │ • Sector limits │  │ • Manual halt  │
│ • Leverage    │  │ • Beta exposure │  │ • Alerts       │
└───────┬───────┘  └────────┬────────┘  └────────┬───────┘
        │                   │                    │
        └───────────────────┼────────────────────┘
                            │
                    ┌───────▼────────┐
                    │ EXECUTION AGENT│
                    ├────────────────┤
                    │ Load brokers   │
                    │ from brokers   │
                    │ .yaml config   │
                    └────────┬───────┘
                             │
        ┌────────────────────┼────────────────────┐
        │                    │                    │
   ┌────▼───┐         ┌─────▼─────┐      ┌──────▼──────┐
   │ ALPACA │         │    IB     │      │ CAPITAL.COM │
   ├────────┤         ├───────────┤      ├─────────────┤
   │ Paper/ │         │ Paper/Live│      │   Leverage  │
   │ Live   │         │ (TWS/GW)  │      │   Forex/CFD │
   └────┬───┘         └─────┬─────┘      └──────┬──────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
                   ┌────────▼────────┐
                   │  BROKER_FILLS   │
                   │  (DB table)     │
                   └────────┬────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
┌───────▼──────┐  ┌────────▼─────┐  ┌──────────▼──────┐
│ PORTFOLIO    │  │  RISK EVENTS │  │  SIGNAL_OUTCOMES│
│ STATE (DB)   │  │  (alerts)    │  │  (for optimizer)│
├──────────────┤  ├──────────────┤  ├─────────────────┤
│ • Cash       │  │ • Drawdown   │  │ • Win/loss      │
│ • Positions  │  │ • Broker fail│  │ • P&L per trade │
│ • Peak value │  │ • Risk limit │  │ • Regime info   │
└──────────────┘  └──────────────┘  └─────────────────┘
```

---

## Component Details

### 1. Data Ingestion (`data/ingest/main.py`)
- **yfinance**: US stocks, ETFs (1-min to daily)
- **Binance WebSocket**: Crypto spot OHLCV real-time
- **Capital.com API**: Forex, commodities via Python SDK
- **Storage**: TimescaleDB (hypertable on `prices` table)
- **Frequency**: Stocks every 1m, crypto every 15s

### 2. Analysis Agents

| Agent | Input | Output | Frequency |
|-------|-------|--------|-----------|
| **Technical** | OHLCV, Vol | MACD cross signals | 2m |
| **Sentiment** | News API, PRAW | Bullish/bearish | 5m |
| **Macro** | FRED API | Regime classification | 5m |
| **Research** | LLM (Ollama) | Thematic opportunities | 10m |
| **News-Momentum** | Sentiment + price momentum | Composite score | 2m |
| **VWAP** | OHLCV | Deviation from daily VWAP | 2m |
| **Supply-Demand** | Swing pivots | Zone-based reversal | 2m |

### 3. Signal Aggregator (`agents/aggregator/main.py`)

```
Per symbol, per regime:

  technical_signal × weight_technical
+ sentiment_signal × weight_sentiment
+ macro_signal × weight_macro
+ research_signal × weight_research
+ news_momentum × weight_news
+ vwap × weight_vwap
+ supply_demand × weight_supply_demand
+ kronos_forecast × weight_kronos
────────────────────────────────────────  = CONSENSUS_SCORE
  sum(all weights)

Thresholds:
  score > +1.5  → BUY signal (confidence = min(80, |score| × 10))
  score < -1.5  → SELL signal
  -1.5 to +1.5  → NEUTRAL (no action)
```

Weights are per-regime (loaded from `agent_params.yaml`):
- **Expansion**: balanced (1.0 each)
- **Crisis**: spike sentiment (2.0), down VWAP (0.3)
- **Pandemic**: max sentiment (2.5), down research (0.8)

### 4. Portfolio Manager → Risk → Execution

```
PORTFOLIO MANAGER (per signal):
  ├─ Current equity: $100k
  ├─ Max position size: 5% per symbol
  ├─ Max sector: 20%
  ├─ Max leverage: 2.0x
  └─ → Proposes trade: BUY 50 AAPL @ limit, 2h GTD

RISK AGENT (validates):
  ├─ Check: portfolio drawdown < 20%
  ├─ Check: beta exposure < 2.0
  ├─ Check: sector concentration OK
  └─ → APPROVE or VETO

CIO (human-in-loop when needed):
  ├─ Auto-approve if confidence > 75%
  ├─ Notify if confidence 50-75% (manual review)
  └─ HALT if confidence < 50%

EXECUTION AGENT:
  ├─ Load enabled brokers from brokers.yaml
  ├─ Fan out trade to ALL brokers in parallel (asyncio.gather)
  ├─ Collect fills (median price used)
  ├─ Write broker_fills table (per-broker result)
  └─ Update portfolio_state (P&L, equity)
```

### 5. Multi-Broker Copy Trading

```
brokers.yaml:
┌────────────────────────────┐
│ - name: investor-john      │
│   type: alpaca             │
│   api_key: PKXXX           │
│   paper: false             │
│                            │
│ - name: investor-sarah     │
│   type: alpaca             │
│   api_key: PKYYY           │
│   paper: false             │
│                            │
│ - name: hedge-ib-live      │
│   type: ib                 │
│   port: 7496 (live)        │
│   client_id: 1             │
└────────────────────────────┘

TRADE EXECUTION:
  trade = {symbol: AAPL, action: long, qty: 50}
  
  brokers = registry.get_all()  # [john, sarah, ib-live]
  
  fills = await asyncio.gather(
    john.fill(trade),
    sarah.fill(trade),
    ib.fill(trade),
    return_exceptions=True
  )
  
  # Each investor gets the same trade at the same time
  # Fills recorded separately, portfolio aggregates
```

---

## Authentication & Dashboard Access

### Login Flow (Google Sign-In)

```
USER → /login → Google OAuth button
         ↓
    User clicks "Sign in with Google"
         ↓
    Google returns ID token
         ↓
    Dashboard POSTs /api/auth/google {credential: token}
         ↓
    Gateway verifies token (Google public keys)
         ↓
    Check: email in ALLOWED_LOGIN_EMAILS
         ↓
    ✓ Issue JWT (bearer token)
         ↓
    Dashboard stores in httpOnly cookie
         ↓
    Redirect to /overview
```

Allowed users from `.env`:
```
ALLOWED_LOGIN_EMAILS=dannjeru555@gmail.com,skaguima4@gmail.com
```

---

## Performance Monitoring

### Real-Time Metrics (Prometheus)

Gateway exposes `/metrics` (15s refresh):

```
hf_agent_up{agent="technical"}            1.0
hf_agent_up{agent="sentiment"}             0.0

hf_portfolio_value_usd                     105230.50
hf_cash_usd                                45000.00
hf_open_positions_count                    3
hf_portfolio_drawdown_pct                  2.34

hf_signals_total{agent="momentum"}         1247
hf_trades_total{status="executed"}         156
hf_pending_trades_count                    2
```

Grafana dashboards:
- **Agent Health**: health gauges, restart counts
- **Trading Activity**: signal/execution rates
- **Portfolio**: equity curve, drawdown, positions

---

## Self-Improving System (Alpha Monitor)

### Daily Performance Analysis

```
ALPHA_MONITOR (daily):
  ├─ Compute: Sharpe ratio (returns / volatility × √252)
  ├─ Compute: Beta vs SPY
  ├─ Compute: Jensen's Alpha (excess return vs beta)
  │
  ├─ Classify TIER:
  │  ├─ Alpha < 2%  → "learning"       (full optimization)
  │  ├─ Alpha ≥ 2%  → "alpha_achieved" (micro-tune only)
  │  └─ Alpha ≥ 5%  → "exceptional"    (parameters locked)
  │
  └─ Email CIO on tier transition
```

### Parameter Optimization

```
AGENT_OPTIMIZER (daily):
  ├─ For each agent per regime:
  │  ├─ Compute: win_rate, avg_pnl (30d)
  │  ├─ For each tunable param:
  │  │  ├─ If low accuracy (< 45%):
  │  │  │  ├─ Propose ±5% adjustment
  │  │  │  ├─ If change ≤ 10%: auto-apply
  │  │  │  └─ If change > 10%: CIO approval
  │  │  └─ Update agent_params.yaml
  │  │
  │  └─ Log to optimizer_history
  │
  └─ Publish: optimizer.proposal events
```

---

## Database Schema (Key Tables)

**Real-Time:**
- `portfolio_state`: hourly snapshots (cash, equity, peak)
- `positions`: open/closed positions with P&L
- `trades`: pending/executed/failed orders
- `broker_fills`: per-broker execution results

**Analysis:**
- `signals`: generated signals (agent, symbol, confidence)
- `signal_outcomes`: win/loss history (for optimizer)
- `prices`: OHLCV hypertable

**Optimization:**
- `optimizer_proposals`: pending CIO decisions
- `optimizer_history`: audit log of param changes
- `risk_events`: drawdowns, broker failures, alerts

---

## Quick Start

**Prerequisites:**
- Python 3.11+
- Docker Desktop (Redis + TimescaleDB)
- [Ollama](https://ollama.ai) locally
- Google OAuth Client ID (see setup below)

**Setup:**

1. Clone repo
2. Copy `.env.example` → `.env` and fill in:
   ```
   GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
   ALLOWED_LOGIN_EMAILS=your@email.com
   ALPACA_API_KEY=<if using Alpaca>
   ```
3. Install: `pip install -r requirements.txt`
4. Start services: `docker compose up -d`
5. Schema: `python scripts/setup_db.py`
6. Models: `ollama pull llama3.1:8b && ollama pull mistral:7b`
7. Agents: `python scripts/start_all.py`
8. Dashboard: `cd dashboard && npm run dev`
9. Open: http://localhost:3000 (Google Sign-In)

**Add broker accounts:**
- Dashboard → **Brokers** tab
- Click **+ Add Broker**
- Select: Alpaca, Interactive Brokers, or Capital.com
- Enter credentials
- Enable accounts → system trades to all simultaneously

**Monitor performance:**
- Dashboard → **Intelligence** tab: Sharpe, Alpha, tier
- Dashboard → **Analytics** tab: equity curve, drawdown
- http://localhost:3001 (Grafana): agent health, trading activity

---

## Key Features

✅ **Multi-Broker Copy Trading**: One signal → All brokers (Alpaca, IB, Capital.com)
✅ **7 Quant Strategies**: Momentum, mean-reversion, ML, Kronos, news-momentum, VWAP, supply-demand
✅ **Regime-Aware**: Parameters tune per macro regime (expansion, crisis, pandemic)
✅ **Self-Improving**: Daily alpha monitoring, auto-optimization, CIO proposals
✅ **Real-Time Monitoring**: Prometheus + Grafana dashboards, email alerts
✅ **Google Sign-In**: Zero-password auth with email allowlist
✅ **Performance Analytics**: Sharpe, Sortino, drawdown, equity curve
✅ **Risk Management**: Portfolio limits, drawdown halt, sector concentration
✅ **Human-in-Loop**: CIO dashboard for manual overrides

---

## Status

| Component | Tests |
|-----------|-------|
| Auth & Dashboard | ✅ 335/335 |
| Multi-Broker Execution | ✅ 17/17 |
| Quant Strategies | ✅ 26/26 |
| Analytics | ✅ 6/6 |
| Monitoring | ✅ 5/5 |
| Optimizer | ✅ 9/9 |

**Total: 335 tests passing** ✅

---

Built with ❤️ using FastAPI, React, TimescaleDB, Ollama, and asyncio.
