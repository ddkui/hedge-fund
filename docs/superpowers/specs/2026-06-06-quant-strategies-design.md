# New Quant Strategies — Design Spec

**Date:** 2026-06-06  
**Status:** Approved  
**Build order:** 4 of 5

---

## Overview

Two new quant strategy agents added to the existing quant layer: **News-Momentum** (combines sentiment scores with price momentum) and **VWAP Deviation** (trades reversion to volume-weighted average price). Both run every 2 minutes, follow the identical `AnalysisAgent` pattern as existing quant agents, and feed into the existing `quant_supervisor` → `aggregator` → `portfolio_mgr` pipeline with no changes to other agents.

---

## Agent 1 — News-Momentum (`agents/quant/news_momentum/`)

### Purpose

Pure price momentum misses directional context from news. Pure sentiment is noisy without price confirmation. Combining both creates a filter that only fires when price movement and market narrative agree.

### Logic

```python
for each symbol in watchlist:
    # Sentiment: latest signal from sentiment agent in last 2h
    sentiment_row = db.fetchrow(
        "SELECT signal_type, confidence FROM signals
         WHERE agent='sentiment' AND symbol=$1
         AND time > now() - INTERVAL '2 hours'
         ORDER BY time DESC LIMIT 1",
        symbol
    )

    # Price momentum: 20-candle rate of change
    prices = db.fetch(
        "SELECT close FROM prices WHERE symbol=$1
         ORDER BY time DESC LIMIT 20", symbol
    )
    price_momentum_pct = (prices[0] - prices[-1]) / prices[-1] * 100

    # Direction-adjust sentiment confidence to [-100, +100]
    if sentiment is bullish:  sentiment_score = +confidence
    if sentiment is bearish:  sentiment_score = -confidence
    if no sentiment:          sentiment_score = 0

    # Composite: sentiment 40%, price momentum 60%
    composite = (sentiment_score * 0.4) + (price_momentum_pct * 0.6)

    # Suppression: if sentiment and price disagree in direction → neutral
    sentiment_dir = sign(sentiment_score)
    momentum_dir  = sign(price_momentum_pct)
    if sentiment_dir != 0 and sentiment_dir != momentum_dir:
        emit neutral_signal, confidence=0
        continue

    THRESHOLD = 1.0  # composite score threshold
    if composite > THRESHOLD:   → bullish_signal
    elif composite < -THRESHOLD: → bearish_signal
    else:                        → neutral_signal

    confidence = min(85, abs(composite) * 8)  # scale to 0-85%
```

### Tunable parameters (auto-tuned by AgentOptimizer)

| Parameter | Default | Range |
|-----------|---------|-------|
| `sentiment_weight` | 0.40 | 0.20–0.60 |
| `momentum_weight` | 0.60 | 0.40–0.80 |
| `momentum_lookback` | 20 candles | 10–50 |
| `composite_threshold` | 1.0 | 0.5–3.0 |
| `sentiment_lookback_hours` | 2h | 1–6h |

### Files

- `agents/quant/news_momentum/__init__.py`
- `agents/quant/news_momentum/agent.py` — `NewsMomentumAgent(AnalysisAgent)`
- `agents/quant/news_momentum/main.py`
- `tests/agents/quant/test_news_momentum.py`

---

## Agent 2 — VWAP Deviation (`agents/quant/vwap/`)

### Purpose

Price tends to revert to the volume-weighted average price (VWAP) within a trading session. Significant deviations above VWAP signal overextension (expect reversion down = bearish). Significant deviations below VWAP signal overselling (expect reversion up = bullish).

### Logic

```python
for each symbol in watchlist:
    # Fetch today's candles (stocks: since market open; crypto: last 24h)
    if asset_class == "stock":
        window_start = today 09:30 UTC-5 (NYSE open)
    else:
        window_start = now() - INTERVAL '24 hours'

    candles = db.fetch(
        "SELECT close, volume FROM prices
         WHERE symbol=$1 AND time >= $2
         ORDER BY time ASC",
        symbol, window_start
    )

    if len(candles) < 5:
        continue  # insufficient intraday data

    # VWAP = sum(close × volume) / sum(volume)
    vwap = sum(c.close * c.volume for c in candles) / sum(c.volume for c in candles)
    current_close = candles[-1].close
    deviation_pct = (current_close - vwap) / vwap * 100

    THRESHOLD = 1.5  # % deviation to trigger signal
    if deviation_pct < -THRESHOLD:
        signal = "bullish_signal"   # below VWAP → expect reversion up
    elif deviation_pct > THRESHOLD:
        signal = "bearish_signal"   # above VWAP → expect reversion down
    else:
        signal = "neutral_signal"

    # Confidence: scales with deviation magnitude, capped at 80%
    confidence = min(80, abs(deviation_pct) * 15)

    reasoning = (
        f"VWAP={vwap:.4f}, current={current_close:.4f}, "
        f"deviation={deviation_pct:+.2f}% — "
        f"{'below' if deviation_pct < 0 else 'above'} VWAP threshold of {THRESHOLD}%"
    )
```

### Tunable parameters (auto-tuned by AgentOptimizer)

| Parameter | Default | Range |
|-----------|---------|-------|
| `deviation_threshold_pct` | 1.5 | 0.5–4.0 |
| `min_candles` | 5 | 3–20 |
| `crypto_window_hours` | 24 | 4–48 |

### Files

- `agents/quant/vwap/__init__.py`
- `agents/quant/vwap/agent.py` — `VWAPDeviationAgent(AnalysisAgent)`
- `agents/quant/vwap/main.py`
- `tests/agents/quant/test_vwap.py`

---

## Integration with Existing Pipeline

Both agents:
1. Call `store_signal()` — writes to `signals` table, publishes to `signals.{agent_name}` Redis channel
2. Are registered in `start_all.py` under "Phase 4a: Quant signal layer"
3. Are added to `KNOWN_AGENT_INTERVALS` in the Engineer agent for health monitoring
4. Are visible to `quant_supervisor` which tracks their Sharpe/win rate and can approve/retire them as algos

Neither agent requires changes to the aggregator, portfolio manager, or execution agent.

---

## Tests

### News-Momentum
- `test_bullish_when_sentiment_and_momentum_agree` — both positive, assert bullish signal
- `test_suppressed_when_sentiment_contradicts_momentum` — divergent directions, assert neutral
- `test_no_signal_without_recent_sentiment` — no sentiment in 2h, assert neutral
- `test_confidence_scales_with_composite_score` — higher composite → higher confidence

### VWAP
- `test_bullish_below_vwap_threshold` — price 2% below VWAP, assert bullish
- `test_bearish_above_vwap_threshold` — price 2% above VWAP, assert bearish
- `test_neutral_within_threshold` — price 0.5% from VWAP, assert neutral
- `test_crypto_uses_24h_window` — asset_class=crypto, assert correct time window
- `test_skips_insufficient_candles` — fewer than 5 candles, assert no signal emitted
- `test_vwap_calculation_correct` — known prices/volumes, assert VWAP formula
