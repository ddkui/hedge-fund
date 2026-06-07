# Phase 3: Optimization

Comprehensive optimization features to improve trading performance and reduce execution costs.

## Features Implemented

### 1. Parameter Auto-Tuning

**Purpose:** Automatically optimize agent parameters when performance degrades.

**How it works:**
- Monitors agent win rate per regime (expansion, crisis, pandemic)
- Proposes parameter changes when win_rate < 45%
- Auto-applies changes < 10%, requires CIO approval >= 10%
- Stores all changes in audit trail (OptimizerHistory table)

**Usage:**
```python
from shared.parameter_tuner import ParameterTuner

tuner = ParameterTuner()
proposal = tuner.propose_change(
    agent="technical",
    regime="expansion",
    parameter="rsi_threshold",
    current_value=30,
    win_rate=0.40  # Poor performance
)

if proposal:
    # Auto-apply if < 10% change
    if not proposal["requires_approval"]:
        apply_to_config(proposal)
    else:
        # Require CIO approval
        send_to_cio(proposal)
```

### 2. ML Regime Prediction

**Purpose:** Predict market regime changes before they occur.

**Detection patterns:**
- VIX spike detection (15 → 35 = crisis)
- Unemployment spike (3.5% → 5.2% = crisis indicator)
- Fed emergency action = crisis
- Stable low-VIX = expansion

**Usage:**
```python
from shared.regime_predictor import RegimePredictor

predictor = RegimePredictor()

# Predict from VIX history
prediction = predictor.predict_next_regime(
    vix_history=[15.0, 18.0, 25.0, 35.0]
)
# Returns: {"predicted_regime": "crisis", "confidence": 0.85, ...}

# Predict from economic data
prediction = predictor.predict_from_economic_data({
    "unemployment_rate": 5.2,
    "previous_unemployment": 3.5,
    "fed_emergency_action": False
})
```

### 3. Multi-Timeframe Signal Combining

**Purpose:** Reduce false signals by combining 5m, 15m, 1h signals.

**Weighting:**
- 5m: 20% weight (most responsive)
- 15m: 30% weight (medium-term)
- 1h: 50% weight (most reliable)

**Conflict detection:**
- Flags if bullish and bearish scores both > 0.4
- Reduces confidence by 30% on conflict

**Usage:**
```python
from shared.signal_combiner import SignalCombiner

combiner = SignalCombiner()

signals = {
    "5m": {"bullish": 0.8},
    "15m": {"bullish": 0.7},
    "1h": {"bullish": 0.9}
}

result = combiner.combine(signals)
# Returns: {"signal": "bullish", "confidence": 0.82, ...}
```

### 4. Order Clustering

**Purpose:** Batch small orders to reduce broker commissions.

**Triggers:**
- Auto-execute when batch value > $10,000
- Auto-execute after 5 minutes holding time
- Calculate commission savings (3 orders @ $5 = $15 vs 1 batch = $5)

**Usage:**
```python
from shared.order_clusterer import OrderClusterer

clusterer = OrderClusterer(min_batch_value=10000)

# Add orders as they come
clusterer.add_order({"symbol": "AAPL", "qty": 50, "price": 150})
clusterer.add_order({"symbol": "MSFT", "qty": 30, "price": 300})

# Get batch when ready
batch = clusterer.get_batch()
if batch:
    execute(batch.orders)
    savings = clusterer.calculate_savings(
        num_orders=2,
        commission_per_order=5,
        batch_commission=5
    )
```

## API Endpoints

### Optimizer Endpoints

```
GET /api/optimizer/proposals - Get pending CIO approvals
POST /api/optimizer/proposals/{id}/approve - Approve parameter change
GET /api/optimizer/history - View all parameter changes
GET /api/optimizer/agents - View agent performance metrics
POST /api/optimizer/backtest - Run optimization backtests
```

## Database Tables

**OptimizerProposal** - Pending parameter optimization proposals
- agent_name, regime, parameter, current_value, proposed_value
- reason, approved (boolean), approved_by, approved_at

**OptimizerHistory** - Audit trail of applied changes
- agent_name, regime, parameter, old_value, new_value
- reason, applied_at

**AgentStats** - Per-agent performance by regime
- agent_name, regime, total_signals, winning_signals, losing_signals
- win_rate, confidence_multiplier, last_updated

## Testing

**Unit tests (50+ total):**
```bash
pytest tests/shared/test_parameter_tuner.py -v
pytest tests/shared/test_regime_predictor.py -v
pytest tests/shared/test_signal_combiner.py -v
pytest tests/shared/test_order_clusterer.py -v
pytest tests/gateway/test_optimizer_router.py -v
pytest tests/test_phase3_integration.py -v
```

## Integration Example

```python
# Full optimization flow
tuner = ParameterTuner()
predictor = RegimePredictor()
combiner = SignalCombiner()
clusterer = OrderClusterer()

# 1. Check if agent needs tuning
proposal = tuner.propose_change("technical", "expansion", "rsi", 30, 0.40)

# 2. Predict regime changes
regime = predictor.predict_next_regime(vix_history)

# 3. Combine timeframe signals
combined_signal = combiner.combine({
    "5m": {"bullish": 0.8},
    "15m": {"bullish": 0.7},
    "1h": {"bullish": 0.9}
})

# 4. Batch orders
clusterer.add_order(trade)
batch = clusterer.get_batch()
if batch:
    execute(batch)
```

## Next Steps

- Integrate with backtesting engine for parameter validation
- Add machine learning model training for regime prediction
- Connect to agent_params.yaml for dynamic parameter updates
- Wire API endpoints to database persistence
- Add Prometheus metrics for tuning activity
