# 10 Architectural Improvements: Implementation Guide

This guide shows how each of the 10 improvements integrates into your hedge fund system.

---

## Overview

```
MARKET DATA
    ↓
ANALYSIS AGENTS
    ↓
SIGNAL AGGREGATOR
    ↓
RISK CHECKS ← [Circuit Breaker, Regime Monitor]
    ↓
PORTFOLIO MANAGER ← [Position Sizer, Trade Audit]
    ↓
EXECUTION ← [Volatility Executor, Broker Failover, Correlation Hedger]
    ↓
FILLS & REPORTING ← [Backtester, Agent Memory, Investor Reports]
```

---

## 1. Circuit Breaker (Loss Limit Safety)

**Purpose:** Halt all trading if portfolio drawdown exceeds threshold (e.g., -5%)

### Setup
```python
from shared.circuit_breaker import CircuitBreaker

cb = CircuitBreaker(max_loss_pct=5.0)  # 5% daily loss limit
```

### Integration Point: Risk Agent
```python
async def risk_check(portfolio_value, peak_value, trade):
    is_tripped, reason = cb.check(portfolio_value, peak_value)
    
    if is_tripped:
        return {"approved": False, "reason": f"Circuit breaker: {reason}"}
    
    # Continue with other risk checks...
```

### Reset at Market Open
```python
# In your market open routine
cb.reset()  # Clear daily trip flag
```

### Key File: `shared/circuit_breaker.py`

---

## 2. Broker Failover & Redundancy

**Purpose:** Automatically retry failed trades on backup brokers

### Setup
```python
from shared.broker_failover import BrokerFailover
from shared.brokers.registry import BrokerRegistry

registry = BrokerRegistry()
brokers = registry.get_all_enabled()
failover = BrokerFailover(brokers)
```

### Integration Point: Execution Agent
```python
async def execute_with_failover(trade):
    # Try all brokers
    fills = await asyncio.gather(
        *[broker.fill(trade) for broker in registry.get_all_enabled()],
        return_exceptions=True
    )
    
    # Retry failures on backup brokers
    filled = await failover.execute_with_failover(trade, fills)
    
    # Dead broker detection
    for fill in filled:
        if fill.status == "error":
            await failover.mark_broker_dead(fill.broker_name)
    
    return filled
```

### Monitor Broker Health
```python
# Periodically check if brokers are back online
dead_brokers = failover.dead_brokers
for broker_name in dead_brokers:
    if await test_broker_connectivity(broker_name):
        await failover.mark_broker_healthy(broker_name)
```

### Key File: `shared/broker_failover.py`

---

## 3. Position Sizing by Account Equity

**Purpose:** Scale order sizes based on each broker's account equity

### Example Scenario
```
Investor John: $100k account → buys 50 AAPL @ $150
Investor Sarah: $500k account → buys 250 AAPL @ $150 (same signal, 5x size)
```

### Setup
```python
from shared.position_sizer import PositionSizer

sizer = PositionSizer(max_position_pct=5.0)  # Max 5% per trade
```

### Integration Point: Portfolio Manager
```python
async def size_positions(signal, broker_equity_map):
    """
    Args:
        signal: {symbol: "AAPL", action: "long", base_qty: 100}
        broker_equity_map: {"alpaca": 100000, "ib": 500000}
    """
    sized_trades = []
    
    for broker_name, equity in broker_equity_map.items():
        adjusted_qty = sizer.calculate_qty(
            signal_qty=signal["base_qty"],
            account_equity=equity,
            price=current_price
        )
        
        sized_trades.append({
            "broker": broker_name,
            "symbol": signal["symbol"],
            "qty": adjusted_qty,
        })
    
    return sized_trades
```

### Alternative: Proportional Scaling
```python
# Use this when all investors follow same base account size
base_equity = 100000
investor_equity = 500000

qty = sizer.scale_qty_by_equity(
    base_qty=100,
    base_equity=base_equity,
    target_equity=investor_equity
)  # Returns 500
```

### Key File: `shared/position_sizer.py`

---

## 4. Intraday Regime Switching

**Purpose:** Adjust parameters dynamically based on market regime

### Regime Classifications
```
EXPANSION:  VIX < 30, normal macro conditions
CRISIS:     VIX 30-50, unemployment spike, or Fed emergency action
PANDEMIC:   VIX > 50, extreme volatility
```

### Setup
```python
from shared.regime_monitor import RegimeMonitor, Regime

monitor = RegimeMonitor()
```

### Integration Point: Signal Aggregator
```python
async def update_regime(vix_value, macro_flags):
    # Update VIX-based regime
    regime = monitor.update_vix(vix_value)
    
    # Check hard flags (unemployment, Fed action, etc)
    if macro_flags:
        regime = monitor.check_hard_flags(macro_flags)
    
    return regime

# In aggregator:
regime = await update_regime(current_vix, macro_flags)
signal_scores = load_signal_weights(regime)  # Load agent_params.yaml per regime
```

### Dynamic Parameter Adjustment
```python
# Load weights from agent_params.yaml based on regime
agent_params = {
    Regime.EXPANSION: {"technical": 1.0, "sentiment": 0.9, ...},
    Regime.CRISIS: {"technical": 0.8, "sentiment": 2.0, ...},  # Sentiment wins in crisis
    Regime.PANDEMIC: {"technical": 0.5, "sentiment": 2.5, ...},
}

params = agent_params[current_regime]
```

### Daily Reset
```python
# At market open
monitor.reset_daily()
```

### Key File: `shared/regime_monitor.py`

---

## 5. Trade Audit Trail

**Purpose:** Record all trade decisions with consensus scores and rejection reasons

### Setup
```python
from shared.trade_audit import TradeAuditLog, TradeAuditRecord

audit_log = TradeAuditLog()
```

### Integration Point: Execution Pipeline
```python
async def execute_with_audit(signal):
    consensus_score = calculate_consensus(signal)
    
    # Log the decision
    record = TradeAuditRecord(
        trade_id=next_id(),
        symbol=signal["symbol"],
        action=signal["action"],
        quantity=signal["qty"],
        consensus_score=consensus_score,
        confidence=signal.get("confidence", 0),
        regime=current_regime,
        agent_signals={
            "technical": signal.get("technical_score"),
            "sentiment": signal.get("sentiment_score"),
            # ... per-agent scores
        },
        status="pending",
    )
    audit_log.add_record(record)
    
    # Risk check
    risk_result = await risk_agent.check(record)
    if not risk_result["approved"]:
        record.status = "rejected"
        record.risk_check_reason = risk_result["reason"]
        audit_log.add_record(record)
        return None
    
    # Execute
    record.status = "executed"
    record.executed_at = datetime.now(timezone.utc)
    audit_log.add_record(record)
    
    return record
```

### Dashboard Integration
```python
# GET /api/dashboard/trades/history
trades = audit_log.get_all()  # Export as dicts for dashboard

# Show rejected trades with reasons
rejected = audit_log.get_rejected()
```

### Key File: `shared/trade_audit.py`

---

## 6. Volatility-Aware Execution

**Purpose:** Use limit orders in high-volatility environments, smart order routing

### Setup
```python
from shared.volatility_executor import VolatilityExecutor

executor = VolatilityExecutor(vix_limit_threshold=25.0)
```

### Order Type Selection
```python
order_type = executor.get_order_type(
    vix=current_vix,
    quantity=trade_qty
)
# Returns: "market", "limit", or "vwap"

# High VIX (> 25) → limit order
# Large order (> 1000 shares) → VWAP
# Small order + normal VIX → market
```

### Limit Price Calculation
```python
current_price = 150.0
limit_price = executor.calculate_limit_price(
    current_price=current_price,
    action="long",
    vix=current_vix
)
# Higher VIX = wider spread tolerance
# Long: limit slightly above market
# Short: limit slightly below market
```

### Integration: Execution Agent
```python
async def place_order(trade, broker):
    vix = await get_vix()
    order_type = executor.get_order_type(vix, trade["qty"])
    
    if order_type == "limit":
        limit = executor.calculate_limit_price(
            trade["price"], trade["action"], vix
        )
        order = {
            "symbol": trade["symbol"],
            "qty": trade["qty"],
            "type": "limit",
            "limit_price": limit,
        }
    elif order_type == "vwap":
        order = {
            "symbol": trade["symbol"],
            "qty": trade["qty"],
            "type": "vwap",
        }
    else:
        order = {
            "symbol": trade["symbol"],
            "qty": trade["qty"],
            "type": "market",
        }
    
    return await broker.place_order(order)
```

### Key File: `shared/volatility_executor.py`

---

## 7. Persistent Agent Memory

**Purpose:** Track agent accuracy and dynamically adjust confidence

### Example
```
Technical Agent (Expansion regime):
  - Total signals: 50
  - Winning signals: 40 (80% win rate)
  - Confidence multiplier: 1.3x (boost strong agent)

Research Agent (Crisis regime):
  - Total signals: 30
  - Winning signals: 8 (27% win rate)
  - Confidence multiplier: 0.6x (penalize weak agent)
```

### Setup
```python
from shared.agent_memory import AgentMemory

memory = AgentMemory()
```

### Track Signal Outcomes
```python
# After trade closes
actual_return = exit_price - entry_price
won = actual_return > 0

memory.update_signal_outcome(
    agent="technical",
    regime="expansion",
    won=won
)
```

### Adjust Agent Confidence
```python
# In signal aggregator:
technical_score = 0.8  # Base score from agent
multiplier = memory.get_confidence_multiplier("technical", "expansion")
adjusted_score = technical_score * multiplier  # 0.8 * 1.3 = 1.04

# Use adjusted_score in consensus calculation
```

### View Agent Stats
```python
stats = memory.get_stats(agent="technical")
for s in stats:
    print(f"{s.agent} ({s.regime}): {s.win_rate:.1%} win rate")
```

### Key File: `shared/agent_memory.py`

---

## 8. Backtesting & Replay

**Purpose:** Test signals against historical prices, compare paper vs real

### Backtest a Trade
```python
from shared.backtester import Backtester, BacktestTrade

backtester = Backtester()

trade = BacktestTrade(
    symbol="AAPL",
    date=datetime(2026, 1, 15),
    action="long",
    entry_price=150.0,
    exit_price=155.0,  # Hypothetical exit
    quantity=100,
)

trade.calculate_pnl()  # $500 profit
backtester.add_trade(trade)
```

### Compare Paper vs Real
```python
paper_trades = [...]  # Simulated execution
real_trades = [...]   # Actual execution

comparison = backtester.compare_paper_vs_real(paper_trades, real_trades)
print(f"Paper P&L: ${comparison['paper_pnl']}")
print(f"Real P&L: ${comparison['real_pnl']}")
print(f"Slippage: {comparison['slippage_pct']:.2f}%")
```

### Calculate Metrics
```python
metrics = backtester.calculate_metrics()
print(f"Total trades: {metrics['total_trades']}")
print(f"Win rate: {metrics['win_rate']:.1%}")
print(f"Total return: {metrics['total_returns_pct']:.2f}%")
```

### Integration: Replay Historical Signals
```python
# Load historical signals from DB
for signal in historical_signals:
    # Get price at signal time
    entry_price = get_price(signal.symbol, signal.time)
    
    # Simulate trade to next signal or day end
    exit_price = get_price(signal.symbol, signal.exit_time)
    
    # Create backtest trade
    bt = BacktestTrade(
        symbol=signal.symbol,
        action=signal.action,
        entry_price=entry_price,
        exit_price=exit_price,
        quantity=signal.qty,
    )
    backtester.add_trade(bt)

# Analyze results
metrics = backtester.calculate_metrics()
```

### Key File: `shared/backtester.py`

---

## 9. Correlation Hedging

**Purpose:** Auto-hedge when portfolio correlation to SPY > 0.8

### Setup
```python
from shared.correlation_hedger import CorrelationHedger

hedger = CorrelationHedger(correlation_threshold=0.8)
```

### Monitor Correlation
```python
# Calculate daily
portfolio_correlation = calc_correlation_to_spy()
hedger.update_correlation(portfolio_correlation)

# Check if hedge needed
if hedger.should_hedge():
    # Current correlation too high, apply hedge
    qty = hedger.calculate_hedge_qty(
        portfolio_value=100000,
        spy_price=400,
        hedge_target_pct=10  # Hedge 10% of portfolio
    )
    
    order = hedger.apply_hedge(qty)
    # → {"symbol": "SPY", "action": "short", "qty": 25}
else:
    # Correlation normalized, remove hedge
    if hedger.is_hedged():
        order = hedger.remove_hedge()
        # → {"symbol": "SPY", "action": "close", "qty": 25}
```

### Integration: Portfolio Risk Monitor
```python
async def risk_monitor_loop():
    while True:
        portfolio_value = await get_portfolio_value()
        correlation = await calculate_correlation()
        hedger.update_correlation(correlation)
        
        current_hedge = hedger.is_hedged()
        should_hedge = hedger.should_hedge()
        
        if should_hedge and not current_hedge:
            # Apply hedge
            qty = hedger.calculate_hedge_qty(portfolio_value, spy_price)
            await execute_spy_short(qty)
            
        elif not should_hedge and current_hedge:
            # Remove hedge
            await close_spy_short()
        
        await asyncio.sleep(3600)  # Check hourly
```

### Key File: `shared/correlation_hedger.py`

---

## 10. Investor Monthly Reporting

**Purpose:** Auto-generate PDF monthly reports with P&L, Sharpe, drawdown, top trades

### Setup
```python
from shared.investor_report import InvestorReportGenerator, MonthlyMetrics, TopTrade

reporter = InvestorReportGenerator("John Doe")
```

### Add Monthly Data
```python
# Collect monthly metrics
metrics = MonthlyMetrics(
    month="2026-06",
    starting_capital=100000,
    ending_capital=105000,
    total_return_pct=5.0,
    monthly_return_pct=5.0,
    sharpe_ratio=1.5,
    sortino_ratio=2.0,
    max_drawdown_pct=3.0,
    win_rate=0.65,
    total_trades=20,
    winning_trades=13,
)
reporter.add_monthly_metrics(metrics)

# Add top 5 trades
top_trades = [
    TopTrade(
        symbol="AAPL",
        entry_date=datetime(2026, 6, 1),
        exit_date=datetime(2026, 6, 5),
        entry_price=150,
        exit_price=160,
        quantity=100,
        pnl=1000,
        returns_pct=6.67,
    ),
    # ... more trades
]
reporter.add_top_trades(top_trades)

# Add regime timeline
reporter.add_regime_changes(
    date=datetime(2026, 6, 10),
    regime="crisis",
    reason="VIX spike to 35"
)
```

### Generate Report
```python
report_data = reporter.get_report_data()
"""
{
    "investor_name": "John Doe",
    "generated_date": "2026-06-07T...",
    "monthly_metrics": [...],
    "top_trades": [...],
    "regime_timeline": [...],
    "summary": {
        "investor": "John Doe",
        "period_return_pct": 5.0,
        "avg_monthly_return_pct": 5.0,
        "avg_sharpe_ratio": 1.5,
        "months_reported": 1,
        "total_trades": 20,
        "total_winning_trades": 13,
    }
}
"""

# Next: Convert to PDF (reportlab library)
# See: https://github.com/ddkui/hedge-fund/blob/main/gateway/routers/reports.py
```

### Integration: Monthly Report Job
```python
# Run on first day of month
async def monthly_report_job():
    # Collect all investor accounts
    investors = await get_all_investor_accounts()
    
    for investor in investors:
        reporter = InvestorReportGenerator(investor.name)
        
        # Get last month's metrics
        metrics = await query_portfolio_metrics(
            investor.account_id,
            start_month=previous_month,
            end_month=previous_month
        )
        reporter.add_monthly_metrics(metrics)
        
        # Get top trades
        top_trades = await get_top_trades(investor.account_id, previous_month)
        reporter.add_top_trades(top_trades)
        
        # Get regime timeline
        regimes = await get_regime_timeline(previous_month)
        for regime_change in regimes:
            reporter.add_regime_changes(
                regime_change.date,
                regime_change.regime,
                regime_change.reason
            )
        
        # Generate and email PDF
        report_data = reporter.get_report_data()
        pdf = generate_pdf(report_data)
        await send_email(investor.email, pdf)
```

### Key File: `shared/investor_report.py`

---

## Integration Flow: End-to-End

```
┌─────────────────────────────────────────────────────────────┐
│ MARKET DATA INGESTION                                        │
│ yfinance, Binance, Capital.com                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ ANALYSIS AGENTS                                              │
│ Technical, Sentiment, Macro, Research, etc                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ SIGNAL AGGREGATOR [Use: Regime Monitor for param tuning]   │
│ Weighted consensus scoring per regime                       │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ PORTFOLIO MANAGER [Use: Position Sizer]                     │
│ Scale positions per broker equity                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ TRADE AUDIT [Use: Trade Audit Trail, Agent Memory]          │
│ Record decisions, confidence, agent contributions           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ RISK CHECKS                                                  │
│ [Use: Circuit Breaker] - Check portfolio drawdown           │
│ [Use: Correlation Hedger] - Auto-hedge if SPY corr > 0.8  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ EXECUTION [Use: Volatility Executor, Broker Failover]       │
│ • Limit orders if VIX > 25                                  │
│ • Smart routing (VWAP/market)                               │
│ • Fail over to backup broker if primary fails               │
│ • Copy trade to all enabled brokers                         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ FILLS & POST-TRADE                                           │
│ [Use: Agent Memory] - Update win rates when trades close   │
│ [Use: Backtester] - Replay signals for research             │
│ [Use: Investor Reports] - Generate monthly PDFs             │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing All Components

See `docs/TESTING.md` for comprehensive testing guide.

All 10 improvements have full test coverage in `tests/shared/test_improvements.py`:

```bash
pytest tests/shared/test_improvements.py -v
```

---

## Configuration

Add to `agent_params.yaml`:

```yaml
# Regime-specific weights (Regime Switching)
regimes:
  expansion:
    technical_weight: 1.0
    sentiment_weight: 0.9
    macro_weight: 0.8
    research_weight: 0.7
  
  crisis:
    technical_weight: 0.8
    sentiment_weight: 2.0  # Sentiment weights heavily in crisis
    macro_weight: 1.5
    research_weight: 0.5
  
  pandemic:
    technical_weight: 0.5
    sentiment_weight: 2.5  # Max sentiment weight
    macro_weight: 2.0
    research_weight: 0.3

# Circuit breaker
circuit_breaker:
  max_loss_pct: 5.0  # Halt at -5% daily loss
  reset_at_market_open: true

# Position sizing
position_sizing:
  max_position_pct: 5.0  # Max 5% per trade
  max_sector_pct: 20.0

# Volatility execution
volatility:
  vix_limit_threshold: 25.0
  large_order_qty: 1000
  small_order_method: "market"
  large_order_method: "vwap"

# Correlation hedging
hedging:
  correlation_threshold: 0.8
  hedge_target_pct: 10.0
```

---

## Summary

| Improvement | File | Purpose | Integration Point |
|------------|------|---------|-------------------|
| Circuit Breaker | `shared/circuit_breaker.py` | Loss limit | Risk Agent |
| Broker Failover | `shared/broker_failover.py` | Redundancy | Execution |
| Position Sizer | `shared/position_sizer.py` | Equity-based scaling | Portfolio Manager |
| Regime Monitor | `shared/regime_monitor.py` | Dynamic params | Aggregator |
| Trade Audit | `shared/trade_audit.py` | Decision log | Everywhere |
| Volatility Executor | `shared/volatility_executor.py` | Smart routing | Execution |
| Agent Memory | `shared/agent_memory.py` | Confidence adjust | Aggregator |
| Backtester | `shared/backtester.py` | Historical replay | Research |
| Correlation Hedger | `shared/correlation_hedger.py` | SPY hedging | Risk Monitor |
| Investor Reports | `shared/investor_report.py` | Monthly PDFs | Scheduled job |

---

Built with ❤️ to make your AI hedge fund more robust, intelligent, and transparent.
