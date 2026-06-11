# AI Hedge Fund - Autonomous Quantitative Trading System

An advanced autonomous AI-powered hedge fund that trades across multiple brokers simultaneously, analyzes market sentiment, executes quantitative strategies, and continuously self-improves through alpha monitoring and academic research integration.

**Status:** 417+ tests passing | Production-ready for paper & live trading | Multi-broker copy-trading + Researcher agents + Hermes self-improvement + Hermes dashboard + Nous Hermes AI integration

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture & Data Flow](#architecture--data-flow)
3. [Core Components](#core-components)
4. [Researcher Agents System](#researcher-agents-system)
5. [API Reference](#api-reference)
6. [Database Schema](#database-schema)
7. [Authentication & Security](#authentication--security)
8. [Performance Monitoring](#performance-monitoring)
9. [Self-Improving System](#self-improving-system)
10. [Quick Start Guide](#quick-start-guide)
11. [Key Features](#key-features)
12. [Testing & Quality](#testing--quality)

---

## System Overview

The hedge fund operates as an integrated system of specialized agents that collaborate to make trading decisions:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│                         AUTONOMOUS HEDGE FUND SYSTEM                            │
├────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  INPUT LAYER: Market Data Ingestion                                     │   │
│  │  ├─ Stocks (yfinance): 1-min to daily OHLCV                           │   │
│  │  ├─ Crypto (Binance): Real-time WebSocket feeds                       │   │
│  │  ├─ Forex/Commodities (Capital.com): API integration                  │   │
│  │  └─ Academic Papers (arXiv/SSRN): Daily researcher agents             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                 ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ANALYSIS LAYER: Signal Generation (7 Agents)                          │   │
│  │  ├─ Technical (MACD, RSI, Bollinger Bands)                            │   │
│  │  ├─ Sentiment (News API, Reddit, Twitter)                            │   │
│  │  ├─ Macro (Fed data, economic indicators)                            │   │
│  │  ├─ News-Momentum (combined sentiment + price)                       │   │
│  │  ├─ VWAP Deviation (volume-weighted average price)                   │   │
│  │  ├─ Supply-Demand (swing pivots, zone analysis)                      │   │
│  │  └─ ML Quant / Kronos AI (neural networks, fine-tuned models)       │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                 ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CONSENSUS LAYER: Weighted Signal Aggregation                          │   │
│  │  Combines all agent signals with regime-specific weights              │   │
│  │  Outputs: Consensus score + confidence level                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                 ↓                                               │
│  ┌──────────────────────┬──────────────────────┬──────────────────────────┐    │
│  │   PORTFOLIO MGR      │    RISK AGENT        │    CIO (Human-Loop)      │    │
│  ├──────────────────────┼──────────────────────┼──────────────────────────┤    │
│  │ • Position sizing    │ • Drawdown limits    │ • Manual override        │    │
│  │ • Leverage control   │ • Sector limits      │ • Approval authority     │    │
│  │ • Max concentration  │ • Beta exposure      │ • Alert notifications    │    │
│  └──────────────────────┴──────────────────────┴──────────────────────────┘    │
│                                 ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  EXECUTION LAYER: Multi-Broker Trade Execution                         │   │
│  │  ├─ Alpaca (stocks, paper/live)                                       │   │
│  │  ├─ Interactive Brokers (stocks, futures, paper/live via TWS)         │   │
│  │  └─ Capital.com (forex, CFDs, leverage)                              │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                 ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  PERSISTENCE LAYER: Database & Audit Trail                            │   │
│  │  ├─ TimescaleDB: Real-time OHLCV data                                 │   │
│  │  ├─ Portfolio state snapshots                                         │   │
│  │  ├─ Trade execution logs                                             │   │
│  │  ├─ Signal outcomes (for optimization)                               │   │
│  │  └─ Risk events & alerts                                             │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                 ↓                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  FEEDBACK LOOP: Self-Improvement & Optimization                        │   │
│  │  ├─ Daily alpha monitoring (Sharpe, Sortino, Jensen's)                │   │
│  │  ├─ Parameter auto-tuning (per-agent, per-regime)                     │   │
│  │  ├─ CIO approval for significant changes (>10%)                       │   │
│  │  └─ Researcher agents for academic insights                          │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                  │
└────────────────────────────────────────────────────────────────────────────────┘
```

---

## Architecture & Data Flow

### Complete Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            MARKET DATA SOURCES                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  yfinance          Binance WS        Capital.com API      arXiv/SSRN       │
│  (Stocks)          (Crypto)          (Forex/CFD)          (Papers)         │
│     │                 │                   │                  │             │
│     └─────────────────┼───────────────────┘──────────────────┘             │
│                       ▼                                                     │
│          ┌────────────────────────────┐                                   │
│          │   DATA INGESTION PIPELINE  │                                   │
│          │  (data/ingest/main.py)     │                                   │
│          │                            │                                   │
│          │  • Parse OHLCV data       │                                   │
│          │  • Normalize timestamps    │                                   │
│          │  • Store to TimescaleDB    │                                   │
│          └────────────────────────────┘                                   │
│                       │                                                     │
└───────────────────────┼─────────────────────────────────────────────────────┘
                        │
                        ▼
        ┌───────────────────────────────┐
        │   TimescaleDB HYPERTABLE      │
        │   (prices table)              │
        │                               │
        │  symbol  │ open │ close │ vol│
        │  ─────────────────────────────│
        │  AAPL    │ 150  │  152  │ 1M │
        │  TSLA    │  240 │  245  │ 2M │
        │  BTC     │45000│ 46000 │10M │
        └───────────────────────────────┘
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    AGENTS (x7)    PORTFOLIO STATE    RESEARCH AGENTS
    ────────────   ────────────────   ────────────────
    Technical      • Cash balance     Supervisor
    Sentiment      • Positions        (quant papers)
    Macro          • Peak value
    News-Mom       • Current P&L      Maintainer
    VWAP                              (system papers)
    Supply-Demand
    ML Quant       ┌──────────────────┐
                   │  SIGNALS TABLE   │
                   │  (per-symbol)    │
                   │  ┌──────────────┐│
                   │  │ direction    ││
                   │  │ confidence   ││
                   │  │ source agent ││
                   │  └──────────────┘│
                   └──────────────────┘
                           │
                        (aggregate)
                           │
                    ┌──────▼──────┐
                    │ AGGREGATOR  │
                    │ Consensus   │
                    │ Score = 75% │
                    │ Action: BUY │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
    PORTFOLIO MGR    RISK AGENT        CIO (HUMAN)
    • Size check     • Drawdown        • Override
    • Leverage OK    • Beta limit      • Veto
                     • Sector OK       • Halt
                           │                 │
                           └────────┬────────┘
                                    ▼
                    ┌──────────────────────────┐
                    │  EXECUTION AGENT        │
                    │  Load brokers.yaml      │
                    │  Fan-out to 3 brokers   │
                    └────────┬─────────────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
    ┌────────┐         ┌──────────┐         ┌────────────┐
    │ ALPACA │         │    IB    │         │ CAPITAL.COM│
    │ (paper)│         │ (live)   │         │ (leverage) │
    └────┬───┘         └────┬─────┘         └────┬───────┘
         │                  │                    │
         └──────────────────┼────────────────────┘
                            ▼
                    ┌──────────────────┐
                    │ BROKER_FILLS     │
                    │ (execution log)  │
                    │ ┌──────────────┐ │
                    │ │ broker       │ │
                    │ │ symbol       │ │
                    │ │ qty, price   │ │
                    │ │ timestamp    │ │
                    │ └──────────────┘ │
                    └────────┬─────────┘
                             │
                    ┌────────▼────────┐
                    │ UPDATE          │
                    │ PORTFOLIO_STATE │
                    │ • New positions │
                    │ • New cash      │
                    │ • P&L calc      │
                    └────────┬────────┘
                             │
        ┌────────────────────┼────────────────────┐
        ▼                    ▼                    ▼
    SIGNAL_OUTCOMES    RISK_EVENTS        MONITORING
    (win/loss)         (drawdown alerts)   (Prometheus)
    (P&L/trade)        (broker failures)   (Grafana)
    (regime)           (position limits)   (email)
```

### Researcher Agents Integration

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    RESEARCHER AGENTS WORKFLOW                            │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ SUPERVISOR RESEARCHER (Daily @ 6 AM UTC)                       │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │                                                                  │   │
│  │  arXiv/SSRN Paper Feeds                                       │   │
│  │         │                                                      │   │
│  │         ├─ "momentum machine learning"                        │   │
│  │         ├─ "mean reversion strategies"                        │   │
│  │         ├─ "pairs trading cointegration"                      │   │
│  │         ├─ "alternative data sentiment"                       │   │
│  │         └─ "deep learning trading"                            │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ FILTER BY RECENCY (last 7 days)  │                         │   │
│  │  │ Keep: 50+ papers                 │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SCORE PAPERS                     │                         │   │
│  │  ├──────────────────────────────────┤                         │   │
│  │  │ relevance_score (0-100)          │  (semantic similarity)  │   │
│  │  │ + academic_score (0-100)         │  (citations + venue)    │   │
│  │  │ + recency_score (0-100)          │  (publication freshness)│   │
│  │  │ = confidence_score (0-100)       │  (weighted avg)        │   │
│  │  │                                  │                         │   │
│  │  │ Formula:                         │                         │   │
│  │  │ confidence = 0.5×rel + 0.3×rec  │                         │   │
│  │  │             + 0.2×acad          │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ FILTER (confidence > 60%)        │                         │   │
│  │  │ Create draft signals             │                         │   │
│  │  │ 2-5 signals typically            │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SAVE TO DATABASE                 │                         │   │
│  │  │ academic_research table          │                         │   │
│  │  │ • paper_id, title, authors       │                         │   │
│  │  │ • relevance, academic, confidence│                         │   │
│  │  │ • strategy_tags, signal_id       │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SLACK ALERT @ 6:30 AM UTC       │                         │   │
│  │  │ "5 new strategy papers"          │                         │   │
│  │  │ • Paper 1 (75% confidence)       │                         │   │
│  │  │ • Paper 2 (72% confidence)       │                         │   │
│  │  │ ...                              │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ MAINTAINER RESEARCHER (Daily @ 6 AM UTC)                       │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │                                                                  │   │
│  │  arXiv/SSRN Paper Feeds                                       │   │
│  │         │                                                      │   │
│  │         ├─ "order execution optimization"                      │   │
│  │         ├─ "market microstructure latency"                     │   │
│  │         ├─ "risk hedging strategies"                          │   │
│  │         ├─ "system architecture patterns"                      │   │
│  │         └─ "distributed computing performance"                │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ FILTER BY RELEVANCE              │                         │   │
│  │  │ Last 30 days, high citations     │                         │   │
│  │  │ Keep: 50+ papers                 │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SCORE PAPERS                     │                         │   │
│  │  ├──────────────────────────────────┤                         │   │
│  │  │ impact_score (0-100)             │  (solves weakness?)     │   │
│  │  │ + feasibility_score (0-100)      │  (<2 weeks to impl?)    │   │
│  │  │ + academic_score (0-100)         │  (peer-reviewed?)       │   │
│  │  │ = combined_score (0-100)         │  (geometric mean)       │   │
│  │  │                                  │                         │   │
│  │  │ combined = ∛(impact × feasibility│                         │   │
│  │  │            × academic)           │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ FILTER (combined_score > 70)     │                         │   │
│  │  │ Auto-create GitHub issues        │                         │   │
│  │  │ 1-3 issues typically             │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SAVE TO DATABASE                 │                         │   │
│  │  │ system_improvements table        │                         │   │
│  │  │ • paper_id, title, authors       │                         │   │
│  │  │ • scores, impact_area            │                         │   │
│  │  │ • implementation_idea, issue_id  │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │         │                                                      │   │
│  │         ▼                                                      │   │
│  │  ┌──────────────────────────────────┐                         │   │
│  │  │ SLACK ALERT @ 6:30 AM UTC       │                         │   │
│  │  │ "3 system improvements found"    │                         │   │
│  │  │ • Issue #234 (execution opt)     │                         │   │
│  │  │ • Issue #235 (risk modeling)     │                         │   │
│  │  │ ...                              │                         │   │
│  │  └──────────────────────────────────┘                         │   │
│  │                                                                  │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Data Ingestion Pipeline (`data/ingest/main.py`)

Ingests market data from multiple sources into TimescaleDB:

```
SOURCE              │  DATA TYPE              │  FREQUENCY  │  RETENTION
────────────────────┼─────────────────────────┼─────────────┼────────────
yfinance            │  Stocks/ETFs (OHLCV)    │  1-min      │  5 years
Binance WebSocket   │  Crypto spot (OHLCV)    │  15s        │  2 years
Capital.com API     │  Forex/CFD (OHLCV)      │  5-min      │  2 years
Fed API (FRED)      │  Economic indicators    │  Daily      │  10 years
NewsAPI/PRAW        │  News/sentiment         │  15-min     │  6 months
```

**Database Design:**

```sql
CREATE TABLE prices (
    time TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    source TEXT,              -- 'yfinance', 'binance', 'capital'
    open NUMERIC,
    high NUMERIC,
    low NUMERIC,
    close NUMERIC,
    volume NUMERIC,
    vwap NUMERIC,
    PRIMARY KEY (time, symbol, source)
);

SELECT create_hypertable('prices', 'time', if_not_exists => TRUE);
CREATE INDEX idx_symbol_time ON prices (symbol, time DESC);
```

### 2. Analysis Agents (7 Specialized Agents)

Each agent produces a signal (-2.0 to +2.0):

```
AGENT               │ INPUT DATA          │ OUTPUT SIGNAL   │ FREQUENCY
────────────────────┼─────────────────────┼─────────────────┼──────────
Technical           │ OHLCV, indicators   │ MACD direction  │ 2 min
Sentiment (NLP)     │ News, social media  │ Bullish/bearish │ 5 min
Macro               │ FRED indicators     │ Regime signal   │ 5 min
Research (LLM)      │ Market context      │ Thematic score  │ 10 min
News-Momentum       │ Sentiment + price   │ Combined score  │ 2 min
VWAP Deviation      │ OHLCV               │ Deviation %     │ 2 min
Supply-Demand       │ Swing pivots        │ Zone breakout   │ 2 min
ML Quant / Kronos   │ Historical prices   │ NN forecast     │ 5 min
```

### 3. Signal Aggregation & Consensus

```
Per Symbol, Per Regime:

    Technical_Signal × weight_technical
  + Sentiment_Signal × weight_sentiment
  + Macro_Signal × weight_macro
  + Research_Signal × weight_research
  + NewsМomentum × weight_news
  + VWAP × weight_vwap
  + SupplyDemand × weight_supply
  + Kronos × weight_kronos
  ──────────────────────────────────────────── = CONSENSUS_SCORE
              sum(all weights)

Decision Thresholds:
    score > +1.5   →  BUY signal     (confidence = min(80, |score| × 10))
    score < -1.5   →  SELL signal    (confidence = min(80, |score| × 10))
    -1.5 to +1.5   →  NEUTRAL        (no action)

Weights Per Regime (agent_params.yaml):
    
    Expansion Regime:    {technical: 1.0, sentiment: 1.0, macro: 1.0, ...}
    Crisis Regime:       {technical: 0.5, sentiment: 2.0, macro: 1.5, ...}
    Pandemic Regime:     {technical: 0.3, sentiment: 2.5, macro: 2.0, ...}
```

### 4. Portfolio Manager & Risk Management

```
┌──────────────────────────────────┐
│ PORTFOLIO MANAGER                │
├──────────────────────────────────┤
│ For each BUY/SELL signal:        │
│                                  │
│ 1. Get current portfolio state  │
│    • Equity: $100,000           │
│    • Cash: $50,000              │
│    • Current positions: 3       │
│                                  │
│ 2. Calculate position size      │
│    • Max per symbol: 5%         │
│    • Max sector: 20%            │
│    • Max leverage: 2.0x         │
│                                  │
│    qty = (equity × 0.05) / price│
│          = ($100k × 0.05) / 150 │
│          = 33 shares            │
│                                  │
│ 3. Check portfolio limits       │
│    ✓ New position = $4,950      │
│    ✓ 4.95% of portfolio OK      │
│    ✓ Sector not overweight      │
│    ✓ Leverage OK (0.98x)        │
│                                  │
│ 4. Propose trade               │
│    BUY 33 AAPL @ limit 150 (2h) │
│                                  │
└──────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────┐
│ RISK AGENT (Validator)           │
├──────────────────────────────────┤
│ Check trade constraints:         │
│                                  │
│ 1. Drawdown check               │
│    Current: -2.5%               │
│    Limit: -20%                  │
│    ✓ OK                         │
│                                  │
│ 2. Beta exposure                │
│    Current beta: 1.2            │
│    Limit: 2.0                   │
│    ✓ OK                         │
│                                  │
│ 3. Sector concentration         │
│    Tech: 18%                    │
│    Limit: 20%                   │
│    ✓ OK                         │
│                                  │
│ 4. Broker limits                │
│    ✓ All brokers have cash      │
│    ✓ Orders within limits       │
│                                  │
│ Decision: APPROVE               │
│                                  │
└──────────────────────────────────┘
         │
         ▼ (confidence > 75%)
┌──────────────────────────────────┐
│ EXECUTION (Parallel Fan-out)     │
├──────────────────────────────────┤
│                                  │
│ await asyncio.gather(            │
│   alpaca.place_order(...),       │
│   ib.place_order(...),           │
│   capital.place_order(...),      │
│   return_exceptions=True         │
│ )                                │
│                                  │
│ Results:                         │
│ • Alpaca: FILLED @ 150.05       │
│ • IB: FILLED @ 150.02           │
│ • Capital: FILLED @ 150.08      │
│                                  │
│ Median fill: $150.05            │
│ Update portfolio state           │
│                                  │
└──────────────────────────────────┘
```

---

## Researcher Agents System

### Supervisor Researcher: Quant Strategy Paper Monitoring

```
DAILY WORKFLOW (6:00 AM UTC)
═════════════════════════════

Step 1: Search Academic Sources
┌─────────────────────────────────┐
│ arXiv Queries:                  │
│ • "momentum machine learning"   │
│ • "mean reversion strategies"   │
│ • "pairs trading cointegration" │
│ • "alternative data sentiment"  │
│ • "deep learning trading"       │
│                                  │
│ SSRN Queries:                   │
│ • "quant strategies"            │
│ • "algorithmic trading"         │
│ • "machine learning finance"    │
│                                  │
│ Results: ~150 papers per day    │
└─────────────────────────────────┘

Step 2: Filter by Recency (Last 7 Days)
┌─────────────────────────────────┐
│ Filter: published_date > now-7d │
│ Results: ~50 papers             │
└─────────────────────────────────┘

Step 3: Score Papers
┌──────────────────────────────────────────────────┐
│ For each paper:                                  │
│                                                  │
│ relevance_score = semantic_similarity(          │
│   paper_abstract,                              │
│   strategy_descriptions                        │
│ ) × 100                                        │
│                                                  │
│ academic_score = (                             │
│   (citations / max_citations) × 0.7 +         │
│   (venue_rank) × 0.3                          │
│ ) × 100                                        │
│                                                  │
│ recency_score = max(0,                         │
│   (7 - days_old) / 7 × 100                    │
│ )                                               │
│                                                  │
│ confidence = (                                  │
│   0.5 × relevance +                            │
│   0.3 × recency +                              │
│   0.2 × academic                               │
│ )                                               │
│                                                  │
│ strategy_tags = auto_tag(abstract)             │
│   → ["momentum", "ml", "signals"]              │
│                                                  │
└──────────────────────────────────────────────────┘

Step 4: Filter & Create Signals (confidence > 60%)
┌────────────────────────────────────┐
│ Keep: Papers with confidence ≥ 60% │
│ Average: 2-5 papers per day        │
│                                     │
│ For each paper:                    │
│ • Create draft trading signal      │
│ • Set strategy_type from tags      │
│ • Generate reasoning               │
│ • Flag for review if conf < 75%    │
│                                     │
└────────────────────────────────────┘

Step 5: Save to Database
┌──────────────────────────────────┐
│ Table: academic_research         │
│                                  │
│ INSERT INTO academic_research:  │
│ • paper_id: "2406.12345"        │
│ • source: "arxiv"               │
│ • title: "ML for Momentum..."   │
│ • authors: "Smith, J.; ..."     │
│ • relevance_score: 82.5         │
│ • academic_score: 78.0          │
│ • confidence_score: 80.3        │
│ • strategy_tags: "momentum,ml" │
│ • generated_signal_id: 1024     │
│ • slack_alert_sent: FALSE       │
│ • date_discovered: now()        │
│                                  │
└──────────────────────────────────┘

Step 6: Slack Alert (6:30 AM UTC)
┌──────────────────────────────────┐
│ Channel: #research               │
│                                  │
│ 📊 Supervisor Researcher Update  │
│ Papers analyzed: 50              │
│ High confidence: 3               │
│ Signals created: 3               │
│                                  │
│ 🔝 Top findings:                │
│ • "ML for Momentum" (80%)        │
│   → Long momentum signals        │
│   https://arxiv.org/abs/...      │
│                                  │
│ • "Pairs Trading Advanced" (75%) │
│   → Market-neutral opportunity   │
│   https://arxiv.org/abs/...      │
│                                  │
│ • "Neural Net Forecasting" (72%) │
│   → Alternative signals          │
│   https://arxiv.org/abs/...      │
│                                  │
└──────────────────────────────────┘
```

### Maintainer Researcher: System Improvement Monitoring

```
DAILY WORKFLOW (6:00 AM UTC)
═════════════════════════════

Step 1: Search for System Improvements
┌────────────────────────────────────┐
│ arXiv Queries:                     │
│ • "order execution optimization"  │
│ • "market microstructure latency" │
│ • "risk hedging strategies"       │
│ • "system architecture patterns"  │
│ • "distributed computing perf"    │
│                                    │
│ Results: ~100 papers per day      │
└────────────────────────────────────┘

Step 2: Filter by Quality & Relevance
┌────────────────────────────────────┐
│ Filter: published > now-30d        │
│ AND citations > 5                  │
│ AND peer-reviewed venues           │
│ Results: ~40 papers                │
└────────────────────────────────────┘

Step 3: Score Papers
┌──────────────────────────────────────┐
│ For each paper:                      │
│                                      │
│ impact_score = solve_weakness_score( │
│   problem_area,                     │
│   current_system_metrics            │
│ ) × 100                             │
│                                      │
│ feasibility_score = (               │
│   can_implement_in_2_weeks?         │
│ ) × 100                             │
│                                      │
│ academic_score = (                  │
│   citations / max_citations +       │
│   venue_tier_score                  │
│ ) × 100                             │
│                                      │
│ combined_score = ∛(                │
│   impact × feasibility × academic   │
│ )  [geometric mean]                 │
│                                      │
│ impact_area = classify(problem)     │
│   → "execution" | "risk" |          │
│   → "architecture" | "performance"  │
│                                      │
└──────────────────────────────────────┘

Step 4: Filter & Create Issues (score > 70)
┌────────────────────────────────────┐
│ Keep: Papers with score ≥ 70       │
│ Average: 1-3 papers per day        │
│                                     │
│ For each paper:                    │
│ • Extract implementation idea      │
│ • Create GitHub issue template     │
│ • Link to paper                    │
│ • Set priority by score            │
│                                     │
└────────────────────────────────────┘

Step 5: Auto-Create GitHub Issues
┌────────────────────────────────────┐
│ Issue Template:                    │
│                                     │
│ Title: "[Exec] VWAP Optimization"  │
│        (prefix by impact_area)     │
│                                     │
│ Body:                              │
│ ## Research Finding               │
│ Paper: "Optimal VWAP Execution"   │
│ Authors: Narang et al. (2023)     │
│                                     │
│ ## Problem                         │
│ Current execution latency: 250ms   │
│ Paper proposes: 50ms improvement  │
│                                     │
│ ## Proposed Solution              │
│ Implement ML-based order sizing    │
│ Reduce VWAP deviation by 20%       │
│                                     │
│ ## Effort Estimate                │
│ ~1 week implementation             │
│                                     │
│ ## References                      │
│ [Link to paper]                    │
│                                     │
│ Labels: execution, research-paper, │
│ priority-high                      │
│                                     │
└────────────────────────────────────┘

Step 6: Save to Database
┌──────────────────────────────────┐
│ Table: system_improvements       │
│                                  │
│ INSERT INTO system_improvements: │
│ • paper_id: "2405.54321"        │
│ • source: "arxiv"               │
│ • title: "VWAP Optimization..."│
│ • impact_area: "execution"      │
│ • impact_score: 92.0            │
│ • feasibility_score: 88.0       │
│ • academic_score: 85.0          │
│ • combined_score: 88.3          │
│ • implementation_idea: "..."    │
│ • github_issue_created: 2847    │
│ • slack_alert_sent: FALSE       │
│ • date_discovered: now()        │
│                                  │
└──────────────────────────────────┘

Step 7: Slack Alert (6:30 AM UTC)
┌──────────────────────────────────┐
│ Channel: #maintenance            │
│                                  │
│ 🔧 Maintainer Researcher Update │
│ Papers analyzed: 40              │
│ High impact: 2                   │
│ Issues created: 2                │
│                                  │
│ 🎯 Top improvements:             │
│ • Issue #234: VWAP Optimization  │
│   (Execution latency -20%)       │
│   Score: 88/100                  │
│                                  │
│ • Issue #235: Risk Hedging Model │
│   (Drawdown protection +15%)     │
│   Score: 82/100                  │
│                                  │
└──────────────────────────────────┘
```

---

## API Reference

### Researcher Agents Endpoints

```
GET /api/research/papers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Query academic papers with pagination and filtering

Query Parameters:
  skip (int):          Pagination offset [default: 0]
  limit (int):         Results per page [default: 10]
  min_confidence (float): Filter by confidence > X [default: 0]
  strategy_tags (str): Filter by tags (comma-separated)
  sort_by (str):       "confidence" | "date" [default: "date"]

Response:
{
  "count": 42,
  "papers": [
    {
      "id": 1,
      "title": "Machine Learning for Momentum Trading",
      "authors": "Smith, J.; Jones, K.",
      "url": "https://arxiv.org/abs/2406.12345",
      "publication_date": "2026-06-07",
      "relevance_score": 82.5,
      "academic_score": 78.0,
      "confidence_score": 80.3,
      "strategy_tags": "momentum,ml",
      "source": "arxiv",
      "date_discovered": "2026-06-08T06:15:00Z"
    },
    ...
  ]
}

───────────────────────────────────────────────

GET /api/research/improvements
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Query system improvements with filtering

Query Parameters:
  skip (int):         Pagination offset [default: 0]
  limit (int):        Results per page [default: 10]
  impact_area (str):  "execution" | "risk" | "architecture" | "performance"
  min_score (float):  Filter by combined_score > X [default: 0]
  github_issue (bool): Show only with/without created issues

Response:
{
  "count": 12,
  "improvements": [
    {
      "id": 1,
      "title": "Low-Latency Order Execution Optimization",
      "authors": "Narang, A.",
      "url": "https://arxiv.org/abs/2405.54321",
      "publication_date": "2026-05-15",
      "impact_area": "execution",
      "impact_score": 92.0,
      "feasibility_score": 88.0,
      "academic_score": 85.0,
      "combined_score": 88.3,
      "implementation_idea": "Implement ML-based order sizing...",
      "github_issue_created": 2847,
      "source": "arxiv",
      "date_discovered": "2026-06-08T06:20:00Z"
    },
    ...
  ]
}

───────────────────────────────────────────────

POST /api/research/run-supervisor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Manually trigger supervisor researcher job

No parameters (runs immediately)

Response:
{
  "status": "completed",
  "papers_fetched": 52,
  "papers_scored": 48,
  "draft_signals_created": 3,
  "research_records_saved": 48,
  "errors": [],
  "execution_time_ms": 15234,
  "timestamp": "2026-06-08T06:15:00Z"
}

───────────────────────────────────────────────

POST /api/research/run-maintainer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Manually trigger maintainer researcher job

No parameters (runs immediately)

Response:
{
  "status": "completed",
  "papers_fetched": 38,
  "papers_scored": 35,
  "github_issues_created": 2,
  "research_records_saved": 35,
  "errors": [],
  "execution_time_ms": 18456,
  "timestamp": "2026-06-08T06:20:00Z"
}
```

### Core Trading Endpoints

```
POST /api/compliance/check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Check trade compliance against SEC/FINRA rules

Request Body:
{
  "symbol": "AAPL",
  "quantity": 100,
  "price": 150.00,
  "action": "BUY",
  "portfolio_value": 100000,
  "current_position_qty": 0,
  "broker_limits": {"margin_available": 50000},
  "day_trades_today": 0
}

Response:
{
  "passes": true,
  "violations": [],
  "warnings": [],
  "max_allowed_notional": 5000,
  "compliance_score": 0.98
}

───────────────────────────────────────────────

GET /api/reporting/form-13f
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Get SEC Form 13F filing (quarterly)

Query Parameters:
  quarter (int): Q1-Q4 [required]
  year (int):    YYYY [required]

Response:
{
  "quarter": 2,
  "year": 2026,
  "filing_date": "2026-08-15",
  "positions": [
    {
      "symbol": "AAPL",
      "cusip": "037833100",
      "shares": 15000,
      "market_value": 2250000,
      "rank": 1
    },
    ...
  ],
  "total_value": 3500000
}
```

---

## Database Schema

### Core Tables

```
┌─────────────────────────────────────┐
│ PRICES (TimescaleDB Hypertable)    │
├─────────────────────────────────────┤
│ time (TIMESTAMPTZ) ............. PK │
│ symbol (TEXT) .................. PK │
│ source (TEXT) .................. PK │
│ open, high, low, close (NUMERIC)   │
│ volume (NUMERIC)                   │
│ vwap (NUMERIC)                     │
│ INDEX: (symbol, time DESC)         │
└─────────────────────────────────────┘

┌──────────────────────────────────┐
│ SIGNALS                          │
├──────────────────────────────────┤
│ id (INT) .................... PK │
│ timestamp (TIMESTAMPTZ)          │
│ symbol (TEXT)                    │
│ agent (TEXT)                     │
│ direction (TEXT: BUY/SELL)       │
│ confidence (FLOAT: 0-100)        │
│ regime (TEXT)                    │
│ forecast_1h (FLOAT)              │
│ forecast_1d (FLOAT)              │
│ INDEX: (symbol, timestamp DESC)  │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ TRADES                           │
├──────────────────────────────────┤
│ id (INT) .................... PK │
│ timestamp (TIMESTAMPTZ)          │
│ symbol (TEXT)                    │
│ action (TEXT: BUY/SELL)          │
│ quantity (INT)                   │
│ target_price (NUMERIC)           │
│ limit_price (NUMERIC)            │
│ status (TEXT)                    │
│ consensus_score (FLOAT)          │
│ agent_signals (JSONB)            │
│ execution_price (NUMERIC)        │
│ execution_qty (INT)              │
│ INDEX: (symbol, timestamp DESC)  │
└──────────────────────────────────┘

┌─────────────────────────────────┐
│ PORTFOLIO_STATE                 │
├─────────────────────────────────┤
│ id (INT) .................. PK │
│ timestamp (TIMESTAMPTZ)          │
│ cash (NUMERIC)                   │
│ equity (NUMERIC)                 │
│ total_value (NUMERIC)            │
│ peak_value (NUMERIC)             │
│ drawdown_pct (FLOAT)             │
│ open_positions (INT)             │
│ leverage (FLOAT)                 │
│ INDEX: (timestamp DESC)          │
└─────────────────────────────────┘

┌──────────────────────────────────┐
│ ACADEMIC_RESEARCH (NEW)          │
├──────────────────────────────────┤
│ id (INT) .................... PK │
│ paper_id (TEXT, UNIQUE)          │
│ source (TEXT)                    │
│ title (TEXT)                     │
│ authors (TEXT)                   │
│ abstract (TEXT)                  │
│ url (TEXT)                       │
│ publication_date (DATE)          │
│ relevance_score (FLOAT: 0-100)   │
│ academic_score (FLOAT: 0-100)    │
│ confidence_score (FLOAT: 0-100)  │
│ strategy_tags (TEXT)             │
│ generated_signal_id (INT, FK)    │
│ slack_alert_sent (BOOL)          │
│ date_discovered (TIMESTAMPTZ)    │
│ INDEX: (confidence_score DESC)   │
│ INDEX: (date_discovered DESC)    │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ SYSTEM_IMPROVEMENTS (NEW)        │
├──────────────────────────────────┤
│ id (INT) .................... PK │
│ paper_id (TEXT, UNIQUE)          │
│ source (TEXT)                    │
│ title (TEXT)                     │
│ authors (TEXT)                   │
│ abstract (TEXT)                  │
│ url (TEXT)                       │
│ publication_date (DATE)          │
│ impact_area (TEXT)               │
│ impact_score (FLOAT: 0-100)      │
│ feasibility_score (FLOAT: 0-100) │
│ academic_score (FLOAT: 0-100)    │
│ combined_score (FLOAT: 0-100)    │
│ implementation_idea (TEXT)       │
│ github_issue_created (INT)       │
│ slack_alert_sent (BOOL)          │
│ date_discovered (TIMESTAMPTZ)    │
│ INDEX: (combined_score DESC)     │
│ INDEX: (impact_area, score DESC) │
└──────────────────────────────────┘
```

---

## Authentication & Security

### Google Sign-In Flow

```
┌──────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION FLOW                       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│  User visits: http://localhost:3000/login                   │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Google Sign-In Button (Frontend)        │               │
│  │ "Sign in with Google"                   │               │
│  └─────────────────────────────────────────┘               │
│         │ (user clicks)                                     │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Google OAuth Consent Screen             │               │
│  │ User authenticates with Google          │               │
│  │ Google returns ID token (JWT)           │               │
│  └─────────────────────────────────────────┘               │
│         │ (token in frontend)                              │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ POST /api/auth/google                   │               │
│  │ {credential: <id_token>}                │               │
│  └─────────────────────────────────────────┘               │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Gateway Verifies Token                  │               │
│  │ • Fetch Google public keys              │               │
│  │ • Verify signature on token             │               │
│  │ • Extract email from token              │               │
│  │ • Check: email ∈ ALLOWED_LOGIN_EMAILS   │               │
│  └─────────────────────────────────────────┘               │
│         │                                                    │
│         ├─ DENY: Return 403 (not allowed)                 │
│         │                                                    │
│         ├─ ALLOW: Continue                                 │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Issue JWT Bearer Token                  │               │
│  │ • Subject: email                        │               │
│  │ • Expires: 24 hours                     │               │
│  │ • Signed with gateway secret            │               │
│  │ Return: {access_token, token_type}      │               │
│  └─────────────────────────────────────────┘               │
│         │ (JWT in response)                                │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Frontend Stores Token                   │               │
│  │ • Cookie (httpOnly, Secure)             │               │
│  │ • localStorage (backup)                 │               │
│  │ Redirect to /overview                   │               │
│  └─────────────────────────────────────────┘               │
│         │                                                    │
│         ▼                                                    │
│  ┌─────────────────────────────────────────┐               │
│  │ Protected API Calls                     │               │
│  │ Authorization: Bearer <jwt_token>       │               │
│  │ Gateway verifies token before response  │               │
│  └─────────────────────────────────────────┘               │
│                                                              │
└──────────────────────────────────────────────────────────────┘
```

### Security Configuration

```env
# .env (required)
GOOGLE_CLIENT_ID=<your-id>.apps.googleusercontent.com
ALLOWED_LOGIN_EMAILS=your@email.com,other@email.com

# .env (optional)
JWT_SECRET=<generate-random-32-char-string>
JWT_EXPIRY=86400  # 24 hours
```

---

## Performance Monitoring

### Prometheus Metrics

```
Gateway exposes /metrics endpoint (Prometheus format, 15s refresh):

PORTFOLIO METRICS:
  hf_portfolio_value_usd ............... 105230.50
  hf_cash_usd .......................... 45000.00
  hf_equity_usd ........................ 60230.50
  hf_open_positions_count ............. 3
  hf_portfolio_drawdown_pct ............ 2.34
  hf_portfolio_max_leverage ............ 1.45
  hf_sector_concentration{sector="tech"} 18.5

TRADING METRICS:
  hf_signals_total{agent="technical"} . 1247
  hf_signals_total{agent="sentiment"} . 956
  hf_trades_total{status="executed"} .. 156
  hf_trades_total{status="pending"} ... 2
  hf_trades_total{status="rejected"} .. 8
  hf_trade_success_rate ............... 0.95

AGENT METRICS:
  hf_agent_up{agent="technical"} ...... 1.0
  hf_agent_up{agent="sentiment"} ...... 1.0
  hf_agent_up{agent="macro"} .......... 0.0  ⚠️ DOWN
  hf_agent_signals{agent="technical"} . 23 (per interval)

COMPLIANCE METRICS:
  hf_compliance_checks_total .......... 1842
  hf_compliance_violations_total ...... 3
  hf_pdt_violations ................... 0

RESEARCH METRICS (NEW):
  hf_research_papers_fetched{agent="supervisor"} ... 52
  hf_research_papers_scored{agent="supervisor"} ... 48
  hf_research_signals_created ........................ 3
  hf_research_improvements_scored ................... 35
  hf_github_issues_created .......................... 2
```

### Grafana Dashboards

```
Dashboard 1: AGENT HEALTH
─────────────────────────
Layout:
  • Agent status gauge (up/down)
  • Signal output per agent
  • Error rate timeline
  • Agent restart count

Dashboard 2: TRADING ACTIVITY
─────────────────────────────
Layout:
  • Signals per day (bar chart)
  • Execution success rate (gauge)
  • Trades by direction (pie chart)
  • Orders pending timeline

Dashboard 3: PORTFOLIO PERFORMANCE
──────────────────────────────────
Layout:
  • Equity curve (line chart, daily)
  • Drawdown graph (area chart)
  • Position breakdown (table)
  • P&L by agent contribution
  • Sector allocation (pie chart)

Dashboard 4: RESEARCHER AGENTS
──────────────────────────────
Layout:
  • Papers analyzed (supervisor vs maintainer)
  • High-confidence signals generated
  • GitHub issues created timeline
  • Impact area distribution
  • Academic quality trends
```

---

## Self-Improving System

The system has two complementary self-improvement agents that run in parallel:

| Agent | Frequency | What it tunes | Trigger |
|---|---|---|---|
| **AgentOptimizer** | 24h | Per-agent parameters (thresholds, lookbacks) | `win_rate < 45%` |
| **Hermes** | 1h | Aggregator consensus weights | `win_rate < 45%` or `> 70%` |

Together they form a full feedback loop: the optimizer sharpens each agent's internal logic while Hermes adjusts how much each agent's signal counts in the final consensus.

### Hermes Agent — Aggregator Weight Tuning + Code Improvement

Hermes runs hourly and has two modes:

**Default (rule-based):** deterministic ±5% weight adjustments based on win rates.

**Nous Hermes mode** (`NOUS_ENABLED=1`): powered by [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent) — an AI agent with a learning loop that uses tools to analyse win rates, tune weights, and propose code improvements autonomously. Falls back to rule-based if the package is unavailable.

```
HOURLY (every 3600s):
═════════════════════════════════════════════════════

           ┌─────────────────────────────────────┐
           │  NOUS_ENABLED=1?                    │
           │  Yes → Nous Hermes AIAgent          │
           │  No  → Rule-based analyzer          │
           └──────────────┬──────────────────────┘
                          ↓
Step 1: Collect win rates (signal_outcomes, last 30 days)
┌──────────────────────────────────────┐
│ technical/expansion  → 72% ✓         │
│ sentiment/expansion  → 41% ✗         │
│ macro/crisis         → 78% ✓         │
│ vwap/contraction     → 38% ✗         │
└──────────────────────────────────────┘
                          ↓
Step 2: Adjust aggregator weights
┌──────────────────────────────────────┐
│ win_rate ≥ 70% → weight × 1.05      │
│ win_rate < 45% → weight × 0.95      │
│ 45–70%         → no change          │
│                                      │
│ Change < 10%  → auto-apply to YAML  │
│ Change ≥ 10%  → queue for CIO       │
└──────────────────────────────────────┘
                          ↓
Step 3: Code improvement (daily, Nous mode)
┌──────────────────────────────────────┐
│ For worst 2 agents (win_rate < 50%): │
│   read_agent_code() → LLM proposes  │
│   minimal fix → stored in           │
│   hermes_patches (pending CIO)      │
└──────────────────────────────────────┘
                          ↓
Step 4: Publish summary → ops.hermes bus
```

**Safety constraints:**
- Weight floor: `0.1` / cap: `2.5`
- Requires ≥ 10 resolved signals before any weight change
- Large weight changes (≥ 10%) always queue for human review
- Code patches never auto-apply — CIO must approve via dashboard
- Only analysis agents are codeable (never execution/risk/portfolio_mgr)

### Hermes Dashboard (`/hermes`)

A dedicated CIO control panel at `/hermes` in the Next.js dashboard:

| Panel | What it does |
|---|---|
| **Win Rate Grid** | Agent × regime win rates (30 days), colour-coded green/yellow/red |
| **Aggregator Weights** | Per-regime inline editing of consensus weights (0.1–2.5) |
| **Pending Proposals** | Approve or reject Hermes weight proposals before they apply |
| **AI Code Patches** | Review AI-generated code diffs, apply to disk or reject |
| **CIO Instructions** | Add/remove instructions injected into every code-improvement prompt |
| **Run Cycle Now** | Manually trigger a Hermes cycle from the dashboard |

API: `GET/PUT /api/hermes/weights` · `GET/POST/DELETE /api/hermes/instructions` · `POST /api/hermes/patches/{id}/apply` · `POST /api/hermes/trigger`

### Nous Hermes Integration

```
┌─────────────────────────────────────────────────────┐
│  NousBridge (agents/hermes/nous_bridge.py)          │
│                                                     │
│  async run_cycle()                                  │
│    │  pre-fetch win rates + YAML (async)            │
│    │                                                │
│    ├─ asyncio.to_thread(AIAgent.run_conversation)   │
│    │   ├─ get_win_rates()      read-only            │
│    │   ├─ get_weights()        read-only            │
│    │   ├─ update_weight()      YAML write (sync)    │
│    │   ├─ queue_weight_proposal() → state list      │
│    │   ├─ read_agent_code()    read-only            │
│    │   └─ propose_code_patch() → state list        │
│    │                                                │
│    └─ flush writes to DB (async)                   │
│        optimizer_history / optimizer_proposals      │
│        hermes_patches                               │
└─────────────────────────────────────────────────────┘

Embedding fixes:
  1. Async   → asyncio.to_thread(); never blocks event loop
  2. Isolation → skip_memory=True + unique session_id per cycle
  3. Tools   → enabled_toolsets=["hedge_fund"] + disabled built-ins
  4. Fallback → NOUS_ENABLED=1 opt-in; errors fall back to rule-based
```

**Setup:**
```bash
uv add --optional nous          # install hermes-agent from GitHub
NOUS_ENABLED=1                  # opt-in via env var
HERMES_MODEL=nous-hermes2       # model in Ollama
uv run scripts/migrate_hermes.py  # create hermes_patches table
```

### Alpha Monitoring Loop

```
DAILY (Midnight UTC):
═════════════════════════════

Step 1: Compute Performance Metrics
┌──────────────────────────────────────┐
│ Analysis Period: Last 30 days        │
│                                      │
│ Returns: daily_pnl / portfolio_value │
│ Volatility: std_dev(returns) × √252 │
│ Sharpe = mean(returns) / volatility  │
│ Beta vs SPY                          │
│ Jensen's Alpha = return - (rf + β×market_return)
│                                      │
│ Results:                             │
│ • Returns: +3.2%                     │
│ • Volatility: 12.5%                  │
│ • Sharpe: 0.82                       │
│ • Beta: 0.95                         │
│ • Alpha: +1.8%                       │
│                                      │
└──────────────────────────────────────┘

Step 2: Classify Tier
┌──────────────────────────────────────┐
│ if alpha < 2%:                       │
│   tier = "learning"                  │
│   action = "full optimization"       │
│                                      │
│ elif alpha >= 2% and alpha < 5%:     │
│   tier = "alpha_achieved"            │
│   action = "micro-tune only"         │
│                                      │
│ elif alpha >= 5%:                    │
│   tier = "exceptional"               │
│   action = "lock parameters"         │
│                                      │
│ Current Tier: "alpha_achieved"       │
│ (Alpha: +1.8% → was 1.6%, improving)│
│                                      │
└──────────────────────────────────────┘

Step 3: Email Notification
┌──────────────────────────────────────┐
│ To: CIO@hedgefund.com                │
│                                      │
│ Subject: Alpha Update - June 2026    │
│                                      │
│ Current Alpha: 1.8%                  │
│ Trend: ↗ (+0.2% from last month)    │
│ Tier: alpha_achieved                 │
│ Status: Stable, optimizing           │
│                                      │
│ Recommendation:                      │
│ Continue micro-tuning, monitor for   │
│ breakthrough to exceptional tier     │
│                                      │
└──────────────────────────────────────┘

Step 4: Parameter Optimization
┌──────────────────────────────────────┐
│ For each agent per regime:           │
│                                      │
│ 1. Compute win rate (last 30d)       │
│    Technical: 52% win rate ✓         │
│                                      │
│ 2. Identify tunable params           │
│    • ma_short (5-20 range)           │
│    • ma_long (20-60 range)           │
│    • rsi_threshold (30-70)           │
│                                      │
│ 3. Calculate param impact            │
│    If win_rate < 45%:               │
│      propose ±5% adjustment         │
│                                      │
│ 4. Auto-apply small changes          │
│    Change < 10%: auto-apply         │
│    Change > 10%: CIO approval       │
│                                      │
│ 5. Update agent_params.yaml          │
│    Commit to optimizer_history       │
│                                      │
│ 6. Email CIO with changes            │
│                                      │
└──────────────────────────────────────┘
```

---

## Quick Start Guide

### Prerequisites

```bash
# Required
- Python 3.11+
- Docker Desktop (Redis + TimescaleDB)
- Node.js 18+ (for dashboard)
- Ollama (locally for research agent)
- Google OAuth Client ID (https://console.cloud.google.com)

# Brokers (at least one required)
- Alpaca account (paper or live)
- Interactive Brokers TWS/GW
- Capital.com account (optional)
```

### Installation Steps

```bash
# 1. Clone and setup
git clone https://github.com/ddkui/hedge-fund.git
cd hedge-fund
cp .env.example .env

# 2. Fill in .env
GOOGLE_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
ALLOWED_LOGIN_EMAILS=your@email.com
ALPACA_API_KEY=<if-using-alpaca>

# 3. Install dependencies
pip install -r requirements.txt
cd dashboard && npm install && cd ..

# 4. Start services
docker compose up -d
# Services available:
#   - TimescaleDB (PostgreSQL): localhost:5432
#   - Redis: localhost:6379
#   - Grafana: http://localhost:3001 (admin/admin)

# 5. Initialize database
python scripts/setup_db.py

# 6. Download ML models (optional, for research agent)
ollama pull llama3.1:8b
ollama pull mistral:7b

# 7. Start all agents
python scripts/start_all.py
# Launches (in parallel):
#   - data/ingest/main.py (price data)
#   - agents/technical/main.py
#   - agents/sentiment/main.py
#   - agents/macro/main.py
#   - ... (all 7 agents)
#   - agents/supervisor_researcher/main.py (6 AM UTC)
#   - agents/maintainer_researcher/main.py (6 AM UTC)
#   - gateway/main.py (FastAPI server on :8000)

# 8. Start dashboard
cd dashboard && npm run dev
# Available at: http://localhost:3000

# 9. Add broker accounts
# Dashboard → Brokers tab → + Add Broker
#   - Select: Alpaca, Interactive Brokers, or Capital.com
#   - Enter credentials
#   - Enable to start trading to all simultaneously
```

---

## Key Features

### ✅ **Multi-Broker Simultaneity**
Execute one signal across Alpaca + IB + Capital.com instantly

### ✅ **7 Quantitative Strategies**
Momentum, mean-reversion, ML quant, Kronos AI, news-momentum, VWAP deviation, supply-demand zones

### ✅ **Regime-Aware Tuning**
Dynamic weight adjustment for expansion, crisis, and pandemic markets

### ✅ **Self-Improving Alpha**
Daily Sharpe/Jensen's alpha calculation, auto-tuning per agent/regime, CIO approval for major changes

### ✅ **Academic Researcher Integration**
Supervisor agent monitors papers on quant strategies (daily), Maintainer agent finds system improvements

### ✅ **Real-Time Monitoring**
Prometheus + Grafana dashboards, email alerts, 403+ automated tests

### ✅ **Zero-Password Auth**
Google Sign-In with email allowlist, no credential storage

### ✅ **Enterprise Risk Controls**
Portfolio limits, drawdown halt, sector concentration, PDT enforcement, position sizing

### ✅ **Audit Trail**
Complete trade decision logs with agent consensus scores, signals, and risk approval

---

## Testing & Quality

### Test Coverage

| Component | Tests | Status |
|-----------|-------|--------|
| Auth & Dashboard | 335 | ✅ |
| Multi-Broker Execution | 17 | ✅ |
| Quant Strategies | 26 | ✅ |
| Analytics | 6 | ✅ |
| Monitoring | 5 | ✅ |
| Optimizer | 9 | ✅ |
| Researcher Agents | 68 | ✅ |

**Total: 403+ tests passing** ✅

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific module
pytest tests/agents/technical/ -v

# With coverage
pytest tests/ --cov=agents --cov=shared --cov=gateway --cov-report=html
```

---

## Architecture Summary

```
┌────────────────────────────────────────────────────────────┐
│                  SYSTEM LAYERS                             │
├────────────────────────────────────────────────────────────┤
│                                                             │
│ Layer 5: UI/UX                                             │
│  └─ React Dashboard (Portfolio, Analytics, Brokers)       │
│                                                             │
│ Layer 4: API Gateway                                      │
│  └─ FastAPI (REST endpoints, compliance, reporting)       │
│     ├─ Research Agents APIs (papers, improvements)        │
│     ├─ Trading APIs (signals, trades)                     │
│     ├─ Reporting APIs (13F, tax, audit)                   │
│     └─ Monitoring APIs (metrics, health)                  │
│                                                             │
│ Layer 3: Decision Logic                                   │
│  └─ Aggregator (consensus scoring)                        │
│     ├─ Portfolio Manager (position sizing)                │
│     ├─ Risk Agent (validation)                            │
│     ├─ CIO (human override)                               │
│     └─ Execution (multi-broker)                           │
│                                                             │
│ Layer 2: Signal Generation                                │
│  ├─ 7 Analysis Agents (parallel)                          │
│  │  ├─ Technical (MACD, RSI)                              │
│  │  ├─ Sentiment (NLP)                                    │
│  │  ├─ Macro (Fed data)                                   │
│  │  ├─ News-Momentum                                      │
│  │  ├─ VWAP Deviation                                     │
│  │  ├─ Supply-Demand                                      │
│  │  └─ ML Quant / Kronos                                  │
│  │                                                         │
│  └─ 2 Researcher Agents (daily @ 6 AM UTC)               │
│     ├─ Supervisor (quant strategies)                      │
│     └─ Maintainer (system improvements)                   │
│                                                             │
│ Layer 1: Data Ingestion                                   │
│  └─ Multi-Source Feeds                                    │
│     ├─ yfinance (stocks)                                  │
│     ├─ Binance (crypto)                                   │
│     ├─ Capital.com (forex/CFD)                            │
│     ├─ NewsAPI/PRAW (sentiment)                           │
│     ├─ arXiv/SSRN (research)                              │
│     └─ TimescaleDB (hypertable storage)                   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

---

Built with ❤️ using FastAPI, React, TimescaleDB, Ollama, asyncio, and autonomous intelligence.

**Status: Production Ready** 🚀
