# gateway/metrics.py
"""
Prometheus metrics for monitoring hedge fund operations.
Exposes metrics for: circuit breaker status, trades, agent health, portfolio, hedging.
"""
from prometheus_client import Counter, Gauge, Histogram
from datetime import datetime, timezone

# Circuit Breaker Metrics
circuit_breaker_trips = Counter(
    "hf_circuit_breaker_trips_total",
    "Total circuit breaker trips",
    ["account_id"],
)

circuit_breaker_active = Gauge(
    "hf_circuit_breaker_active",
    "Is circuit breaker currently active (1=tripped, 0=ok)",
    ["account_id"],
)

# Portfolio Metrics
portfolio_value_usd = Gauge(
    "hf_portfolio_value_usd",
    "Current portfolio total value",
    ["account_id"],
)

portfolio_cash_usd = Gauge(
    "hf_portfolio_cash_usd",
    "Available cash",
    ["account_id"],
)

portfolio_drawdown_pct = Gauge(
    "hf_portfolio_drawdown_pct",
    "Current portfolio drawdown percentage",
    ["account_id"],
)

open_positions_count = Gauge(
    "hf_open_positions_count",
    "Number of open positions",
    ["account_id"],
)

# Trade Metrics
trades_total = Counter(
    "hf_trades_total",
    "Total trades executed",
    ["account_id", "status"],
)

trades_rejected_total = Counter(
    "hf_trades_rejected_total",
    "Total rejected trades",
    ["account_id", "reason"],
)

trade_pnl = Histogram(
    "hf_trade_pnl_usd",
    "Trade P&L distribution",
    ["account_id"],
    buckets=(-1000, -500, -100, 0, 100, 500, 1000),
)

# Agent Metrics
agent_signals_total = Counter(
    "hf_agent_signals_total",
    "Total signals generated",
    ["agent", "regime", "signal_type"],
)

agent_confidence_avg = Gauge(
    "hf_agent_confidence_avg",
    "Average signal confidence",
    ["agent", "regime"],
)

agent_win_rate = Gauge(
    "hf_agent_win_rate",
    "Agent signal win rate",
    ["agent", "regime"],
)

agent_up = Gauge(
    "hf_agent_up",
    "Is agent responding (1=up, 0=down)",
    ["agent"],
)

# Broker Metrics
broker_fills_total = Counter(
    "hf_broker_fills_total",
    "Total broker fills",
    ["broker", "status"],
)

broker_fill_price_deviation = Histogram(
    "hf_broker_fill_price_deviation_pct",
    "Broker fill price deviation from signal price",
    ["broker"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

broker_available = Gauge(
    "hf_broker_available",
    "Is broker available (1=up, 0=down)",
    ["broker"],
)

broker_failover_count = Counter(
    "hf_broker_failover_count",
    "Number of failovers to backup broker",
    ["broker"],
)

# Hedging Metrics
correlation_hedge_active = Gauge(
    "hf_correlation_hedge_active",
    "Is correlation hedge currently active (1=yes, 0=no)",
)

correlation_to_spy = Gauge(
    "hf_correlation_to_spy",
    "Current portfolio correlation to SPY",
)

spy_short_quantity = Gauge(
    "hf_spy_short_quantity",
    "Current SPY short hedge quantity",
)

hedge_activation_total = Counter(
    "hf_hedge_activation_total",
    "Total hedge activations",
)

# Risk Metrics
max_loss_limit_pct = Gauge(
    "hf_max_loss_limit_pct",
    "Maximum daily loss limit percentage",
)

risk_events_total = Counter(
    "hf_risk_events_total",
    "Total risk events logged",
    ["event_type", "severity"],
)

# Regime Metrics
current_regime = Gauge(
    "hf_current_regime",
    "Current market regime (0=expansion, 1=crisis, 2=pandemic)",
)

vix_level = Gauge(
    "hf_vix_level",
    "Current VIX level",
)

regime_changes_total = Counter(
    "hf_regime_changes_total",
    "Total regime changes",
    ["old_regime", "new_regime"],
)

# Performance Metrics
daily_pnl_usd = Gauge(
    "hf_daily_pnl_usd",
    "Daily profit/loss",
    ["account_id"],
)

monthly_return_pct = Gauge(
    "hf_monthly_return_pct",
    "Month-to-date return percentage",
    ["account_id"],
)

sharpe_ratio = Gauge(
    "hf_sharpe_ratio",
    "Current Sharpe ratio",
    ["account_id"],
)

alpha_pct = Gauge(
    "hf_alpha_pct",
    "Jensen's Alpha percentage",
    ["account_id"],
)

# Health Metrics
api_requests_total = Counter(
    "hf_api_requests_total",
    "Total API requests",
    ["endpoint", "method", "status"],
)

api_request_duration_seconds = Histogram(
    "hf_api_request_duration_seconds",
    "API request latency",
    ["endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

database_queries_total = Counter(
    "hf_database_queries_total",
    "Total database queries",
    ["table", "operation"],
)

database_query_duration_seconds = Histogram(
    "hf_database_query_duration_seconds",
    "Database query latency",
    ["table"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5),
)


# Helper functions to record metrics

def record_circuit_breaker_trip(account_id: str):
    """Record circuit breaker trip."""
    circuit_breaker_trips.labels(account_id=account_id).inc()
    circuit_breaker_active.labels(account_id=account_id).set(1)


def record_circuit_breaker_reset(account_id: str):
    """Record circuit breaker reset."""
    circuit_breaker_active.labels(account_id=account_id).set(0)


def record_trade_executed(account_id: str, pnl: float):
    """Record executed trade."""
    trades_total.labels(account_id=account_id, status="executed").inc()
    if pnl:
        trade_pnl.labels(account_id=account_id).observe(pnl)


def record_trade_rejected(account_id: str, reason: str):
    """Record rejected trade."""
    trades_total.labels(account_id=account_id, status="rejected").inc()
    trades_rejected_total.labels(account_id=account_id, reason=reason).inc()


def record_agent_signal(agent: str, regime: str, signal_type: str, confidence: float):
    """Record agent signal."""
    agent_signals_total.labels(agent=agent, regime=regime, signal_type=signal_type).inc()
    agent_confidence_avg.labels(agent=agent, regime=regime).set(confidence)


def record_broker_fill(broker: str, status: str, price_deviation_pct: float = None):
    """Record broker fill."""
    broker_fills_total.labels(broker=broker, status=status).inc()
    if price_deviation_pct is not None:
        broker_fill_price_deviation.labels(broker=broker).observe(price_deviation_pct)


def record_broker_failover(broker: str):
    """Record broker failover."""
    broker_failover_count.labels(broker=broker).inc()


def record_hedge_activation(correlation: float, spy_qty: float):
    """Record hedge activation."""
    correlation_hedge_active.set(1)
    correlation_to_spy.set(correlation)
    spy_short_quantity.set(spy_qty)
    hedge_activation_total.inc()


def record_hedge_deactivation():
    """Record hedge deactivation."""
    correlation_hedge_active.set(0)
    spy_short_quantity.set(0)


def record_regime_change(old_regime: str, new_regime: str, vix: float):
    """Record regime change."""
    regime_changes_total.labels(old_regime=old_regime, new_regime=new_regime).inc()
    # Map regime to number
    regime_map = {"expansion": 0, "crisis": 1, "pandemic": 2}
    current_regime.set(regime_map.get(new_regime, 0))
    vix_level.set(vix)


def record_risk_event(event_type: str, severity: str):
    """Record risk event."""
    risk_events_total.labels(event_type=event_type, severity=severity).inc()
