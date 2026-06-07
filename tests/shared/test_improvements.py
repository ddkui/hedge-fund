# tests/shared/test_improvements.py
"""
Comprehensive tests for all 10 architectural improvements.
Tests are modular and extensible - add new test cases without breaking existing ones.
"""
import pytest
from datetime import datetime, timezone
from shared.circuit_breaker import CircuitBreaker
from shared.broker_failover import BrokerFailover
from shared.position_sizer import PositionSizer
from shared.regime_monitor import RegimeMonitor, Regime
from shared.trade_audit import TradeAuditLog, TradeAuditRecord
from shared.volatility_executor import VolatilityExecutor
from shared.agent_memory import AgentMemory
from shared.backtester import Backtester, BacktestTrade
from shared.correlation_hedger import CorrelationHedger
from shared.investor_report import InvestorReportGenerator, MonthlyMetrics


# ============================================================================
# CIRCUIT BREAKER TESTS
# ============================================================================

class TestCircuitBreaker:
    """Test loss-limit circuit breaker."""

    def test_circuit_not_tripped_within_loss_limit(self):
        """Circuit should allow trading when loss < limit."""
        cb = CircuitBreaker(max_loss_pct=5.0)
        is_tripped, reason = cb.check(
            portfolio_value=100000,
            peak_value=102000
        )
        assert not is_tripped
        assert "OK" in reason

    def test_circuit_trips_at_loss_limit(self):
        """Circuit should trip when loss >= limit."""
        cb = CircuitBreaker(max_loss_pct=5.0)
        is_tripped, reason = cb.check(
            portfolio_value=95000,
            peak_value=100000
        )
        assert is_tripped
        assert "exceeds" in reason

    def test_circuit_reset(self):
        """Circuit should reset for next day."""
        cb = CircuitBreaker(max_loss_pct=5.0)
        cb.check(portfolio_value=95000, peak_value=100000)
        assert cb.is_tripped()
        cb.reset()
        assert not cb.is_tripped()

    def test_circuit_stays_tripped(self):
        """Tripped circuit should stay tripped until reset."""
        cb = CircuitBreaker(max_loss_pct=5.0)
        cb.check(portfolio_value=95000, peak_value=100000)
        is_tripped, _ = cb.check(portfolio_value=98000, peak_value=100000)
        assert is_tripped


# ============================================================================
# BROKER FAILOVER TESTS
# ============================================================================

class TestBrokerFailover:
    """Test failover to backup brokers on failure."""

    @pytest.mark.asyncio
    async def test_no_failover_on_successful_fills(self):
        """No failover needed when brokers succeed."""
        from unittest.mock import AsyncMock
        broker = AsyncMock()
        broker.name = "alpaca"
        failover = BrokerFailover([broker])

        from shared.brokers.base import BrokerFill
        successful_fills = [
            BrokerFill(broker_name="alpaca", status="filled", fill_price=100.0, error_msg=None)
        ]

        result = await failover.execute_with_failover({}, successful_fills)
        assert len(result) == 1
        assert result[0].status == "filled"

    @pytest.mark.asyncio
    async def test_broker_marked_dead(self):
        """Broker should be marked dead after failures."""
        broker = AsyncMock()
        broker.name = "alpaca"
        failover = BrokerFailover([broker])

        await failover.mark_broker_dead("alpaca")
        available = await failover.get_available_brokers()
        assert len(available) == 0

    @pytest.mark.asyncio
    async def test_broker_recovery(self):
        """Dead broker should be restored to healthy."""
        broker = AsyncMock()
        broker.name = "alpaca"
        failover = BrokerFailover([broker])

        await failover.mark_broker_dead("alpaca")
        await failover.mark_broker_healthy("alpaca")
        available = await failover.get_available_brokers()
        assert len(available) == 1


# ============================================================================
# POSITION SIZING TESTS
# ============================================================================

class TestPositionSizer:
    """Test position sizing by account equity."""

    def test_position_respects_max_percentage(self):
        """Position size should not exceed max % of equity."""
        sizer = PositionSizer(max_position_pct=5.0)
        qty = sizer.calculate_qty(
            signal_qty=100,
            account_equity=100000,
            price=100
        )
        # Max position = 5% * $100k / $100 = 50 shares
        assert qty <= 50

    def test_proportional_scaling(self):
        """Qty should scale proportionally with equity."""
        sizer = PositionSizer()
        qty_100k = sizer.scale_qty_by_equity(100, 100000, 100000)
        qty_500k = sizer.scale_qty_by_equity(100, 100000, 500000)

        assert qty_500k == 500  # 5x equity = 5x qty
        assert qty_100k == 100

    def test_zero_equity_handling(self):
        """Should handle zero equity gracefully."""
        sizer = PositionSizer()
        qty = sizer.calculate_qty(100, 0, 100)
        assert qty == 0

    def test_small_account_respects_limit(self):
        """Small account should still respect max position %."""
        sizer = PositionSizer(max_position_pct=10.0)
        qty = sizer.calculate_qty(100, 1000, 10)
        # Max = 10% * $1000 / $10 = 10 shares
        assert qty <= 10


# ============================================================================
# REGIME SWITCHING TESTS
# ============================================================================

class TestRegimeMonitor:
    """Test intraday regime switching."""

    def test_normal_vix_stays_expansion(self):
        """Normal VIX should keep expansion regime."""
        monitor = RegimeMonitor()
        regime = monitor.update_vix(15.0)
        assert regime == Regime.EXPANSION

    def test_elevated_vix_triggers_crisis(self):
        """VIX > 30 should trigger crisis regime."""
        monitor = RegimeMonitor()
        regime = monitor.update_vix(35.0)
        assert regime == Regime.CRISIS

    def test_high_vix_triggers_panic(self):
        """VIX > 50 should trigger pandemic regime."""
        monitor = RegimeMonitor()
        regime = monitor.update_vix(60.0)
        assert regime == Regime.PANDEMIC

    def test_hard_flags_override_vix(self):
        """Hard flags (unemployment) should force crisis."""
        monitor = RegimeMonitor()
        monitor.update_vix(15.0)  # Normal
        regime = monitor.check_hard_flags({
            "unemployment_spike": True,
            "fed_emergency_action": False
        })
        assert regime == Regime.CRISIS

    def test_daily_reset(self):
        """Daily reset should clear intraday flags."""
        monitor = RegimeMonitor()
        monitor.check_hard_flags({"unemployment_spike": True})
        monitor.reset_daily()
        assert not monitor.hard_flags["unemployment_spike"]


# ============================================================================
# TRADE AUDIT TESTS
# ============================================================================

class TestTradeAudit:
    """Test trade audit trail."""

    def test_add_executed_trade(self):
        """Should log executed trades with consensus."""
        log = TradeAuditLog()
        record = TradeAuditRecord(
            trade_id=1,
            symbol="AAPL",
            action="long",
            quantity=100,
            consensus_score=2.5,
            confidence=75.0,
            regime="expansion",
            agent_signals={"technical": 0.8, "sentiment": 0.7},
            status="executed",
        )
        log.add_record(record)
        assert len(log.records) == 1

    def test_add_rejected_trade(self):
        """Should log rejected trades with reasons."""
        log = TradeAuditLog()
        record = TradeAuditRecord(
            trade_id=2,
            symbol="TSLA",
            action="short",
            quantity=50,
            consensus_score=0.8,
            confidence=40.0,
            regime="expansion",
            agent_signals={},
            status="rejected",
            rejection_reason="Low confidence < 50%",
        )
        log.add_record(record)
        rejected = log.get_rejected()
        assert len(rejected) == 1
        assert "Low confidence" in rejected[0].rejection_reason

    def test_get_by_symbol(self):
        """Should retrieve trades by symbol."""
        log = TradeAuditLog()
        log.add_record(TradeAuditRecord(
            trade_id=1, symbol="AAPL", action="long", quantity=100,
            consensus_score=2.0, confidence=80.0, regime="expansion",
            agent_signals={}, status="executed"
        ))
        log.add_record(TradeAuditRecord(
            trade_id=2, symbol="MSFT", action="long", quantity=50,
            consensus_score=1.5, confidence=70.0, regime="expansion",
            agent_signals={}, status="executed"
        ))

        aapl = log.get_by_symbol("AAPL")
        assert len(aapl) == 1
        assert aapl[0].symbol == "AAPL"

    def test_export_to_dict(self):
        """Should export audit records as dicts."""
        log = TradeAuditLog()
        log.add_record(TradeAuditRecord(
            trade_id=1, symbol="AAPL", action="long", quantity=100,
            consensus_score=2.0, confidence=80.0, regime="expansion",
            agent_signals={}, status="executed"
        ))

        dicts = log.get_all()
        assert len(dicts) == 1
        assert dicts[0]["symbol"] == "AAPL"
        assert isinstance(dicts[0]["created_at"], str)


# ============================================================================
# VOLATILITY-AWARE EXECUTION TESTS
# ============================================================================

class TestVolatilityExecutor:
    """Test volatility-aware order routing."""

    def test_market_order_low_vix(self):
        """Low VIX + small qty = market order."""
        executor = VolatilityExecutor(vix_limit_threshold=25.0)
        order_type = executor.get_order_type(vix=15.0, quantity=100)
        assert order_type == "market"

    def test_limit_order_high_vix(self):
        """High VIX = limit order regardless of size."""
        executor = VolatilityExecutor(vix_limit_threshold=25.0)
        order_type = executor.get_order_type(vix=35.0, quantity=100)
        assert order_type == "limit"

    def test_vwap_large_order(self):
        """Large order + normal VIX = VWAP."""
        executor = VolatilityExecutor()
        order_type = executor.get_order_type(vix=15.0, quantity=2000)
        assert order_type == "vwap"

    def test_limit_price_for_long(self):
        """Long order limit price should be above market."""
        executor = VolatilityExecutor()
        limit = executor.calculate_limit_price(100.0, "long", vix=30)
        assert limit > 100.0

    def test_limit_price_for_short(self):
        """Short order limit price should be below market."""
        executor = VolatilityExecutor()
        limit = executor.calculate_limit_price(100.0, "short", vix=30)
        assert limit < 100.0


# ============================================================================
# AGENT MEMORY TESTS
# ============================================================================

class TestAgentMemory:
    """Test persistent agent memory for confidence adjustment."""

    def test_track_win_rate(self):
        """Should track signal win rates per agent/regime."""
        memory = AgentMemory()
        for _ in range(8):
            memory.update_signal_outcome("technical", "expansion", True)
        for _ in range(2):
            memory.update_signal_outcome("technical", "expansion", False)

        stats = memory.get_stats("technical", "expansion")[0]
        assert stats.win_rate == 0.8

    def test_confidence_multiplier_strong(self):
        """Strong track record (70%+) should boost confidence."""
        memory = AgentMemory()
        for _ in range(14):
            memory.update_signal_outcome("sentiment", "expansion", True)
        for _ in range(6):
            memory.update_signal_outcome("sentiment", "expansion", False)

        multiplier = memory.get_confidence_multiplier("sentiment", "expansion")
        assert multiplier == 1.3

    def test_confidence_multiplier_poor(self):
        """Poor track record should reduce confidence."""
        memory = AgentMemory()
        for _ in range(3):
            memory.update_signal_outcome("research", "crisis", True)
        for _ in range(7):
            memory.update_signal_outcome("research", "crisis", False)

        multiplier = memory.get_confidence_multiplier("research", "crisis")
        assert multiplier < 1.0

    def test_insufficient_data_neutral(self):
        """Less than 10 signals = neutral multiplier."""
        memory = AgentMemory()
        memory.update_signal_outcome("macro", "expansion", True)
        multiplier = memory.get_confidence_multiplier("macro", "expansion")
        assert multiplier == 1.0


# ============================================================================
# BACKTESTER TESTS
# ============================================================================

class TestBacktester:
    """Test backtesting and replay functionality."""

    def test_calculate_long_pnl(self):
        """Should calculate P&L for long trade."""
        trade = BacktestTrade(
            symbol="AAPL",
            date=datetime.now(timezone.utc),
            action="long",
            entry_price=100.0,
            exit_price=110.0,
            quantity=10.0,
        )
        pnl = trade.calculate_pnl()
        assert pnl == 100.0  # (110-100) * 10

    def test_calculate_short_pnl(self):
        """Should calculate P&L for short trade (reversed)."""
        trade = BacktestTrade(
            symbol="AAPL",
            date=datetime.now(timezone.utc),
            action="short",
            entry_price=100.0,
            exit_price=90.0,
            quantity=10.0,
        )
        pnl = trade.calculate_pnl()
        assert pnl == 100.0  # Profit on short

    def test_backtest_metrics(self):
        """Should calculate aggregated metrics."""
        backtester = Backtester()

        # Add winning trade
        trade1 = BacktestTrade(
            symbol="AAPL",
            date=datetime.now(timezone.utc),
            action="long",
            entry_price=100,
            exit_price=110,
            quantity=10,
        )
        trade1.calculate_pnl()
        backtester.add_trade(trade1)

        # Add losing trade
        trade2 = BacktestTrade(
            symbol="MSFT",
            date=datetime.now(timezone.utc),
            action="long",
            entry_price=100,
            exit_price=95,
            quantity=10,
        )
        trade2.calculate_pnl()
        backtester.add_trade(trade2)

        metrics = backtester.calculate_metrics()
        assert metrics["total_trades"] == 2
        assert metrics["winning_trades"] == 1
        assert metrics["win_rate"] == 0.5

    def test_paper_vs_real_comparison(self):
        """Should compare paper vs real execution."""
        paper_trade = BacktestTrade(
            symbol="AAPL", date=datetime.now(timezone.utc), action="long",
            entry_price=100, exit_price=105, quantity=10
        )
        paper_trade.calculate_pnl()

        real_trade = BacktestTrade(
            symbol="AAPL", date=datetime.now(timezone.utc), action="long",
            entry_price=100, exit_price=104, quantity=10
        )
        real_trade.calculate_pnl()

        backtester = Backtester()
        comparison = backtester.compare_paper_vs_real([paper_trade], [real_trade])

        assert comparison["paper_pnl"] == 50  # 5 * 10
        assert comparison["real_pnl"] == 40   # 4 * 10
        assert comparison["difference"] == -10


# ============================================================================
# CORRELATION HEDGING TESTS
# ============================================================================

class TestCorrelationHedger:
    """Test correlation-based hedging."""

    def test_hedge_triggers_above_threshold(self):
        """Hedge should activate when correlation > threshold."""
        hedger = CorrelationHedger(correlation_threshold=0.8)
        hedger.update_correlation(0.85)
        assert hedger.should_hedge()

    def test_hedge_inactive_below_threshold(self):
        """Hedge should not trigger when correlation < threshold."""
        hedger = CorrelationHedger(correlation_threshold=0.8)
        hedger.update_correlation(0.75)
        assert not hedger.should_hedge()

    def test_calculate_spy_short_qty(self):
        """Should calculate SPY short qty based on portfolio size."""
        hedger = CorrelationHedger()
        qty = hedger.calculate_hedge_qty(
            portfolio_value=100000,
            spy_price=400,
            hedge_target_pct=10
        )
        # 10% * $100k / $400 = 25 shares
        assert qty == 25

    def test_apply_and_remove_hedge(self):
        """Should apply and remove hedge."""
        hedger = CorrelationHedger()

        hedge = hedger.apply_hedge(50)
        assert hedger.is_hedged()
        assert hedge["action"] == "short"

        close = hedger.remove_hedge()
        assert not hedger.is_hedged()
        assert close["action"] == "close"


# ============================================================================
# INVESTOR REPORTING TESTS
# ============================================================================

class TestInvestorReporting:
    """Test monthly investor reporting."""

    def test_add_monthly_metrics(self):
        """Should aggregate monthly performance."""
        reporter = InvestorReportGenerator("John Doe")
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
        assert len(reporter.monthly_metrics) == 1

    def test_top_trades_ranking(self):
        """Should rank top trades by P&L."""
        reporter = InvestorReportGenerator("Jane Smith")

        from shared.investor_report import TopTrade
        trades = [
            TopTrade(
                symbol="AAPL", entry_date=datetime.now(timezone.utc),
                exit_date=datetime.now(timezone.utc),
                entry_price=100, exit_price=110, quantity=10, pnl=100, returns_pct=10
            ),
            TopTrade(
                symbol="MSFT", entry_date=datetime.now(timezone.utc),
                exit_date=datetime.now(timezone.utc),
                entry_price=100, exit_price=115, quantity=10, pnl=150, returns_pct=15
            ),
        ]
        reporter.add_top_trades(trades)
        assert len(reporter.top_trades) == 2
        assert reporter.top_trades[0].pnl > reporter.top_trades[1].pnl

    def test_generate_report_data(self):
        """Should export complete report data."""
        reporter = InvestorReportGenerator("Bob Johnson")
        metrics = MonthlyMetrics(
            month="2026-06", starting_capital=100000, ending_capital=105000,
            total_return_pct=5.0, monthly_return_pct=5.0, sharpe_ratio=1.5,
            sortino_ratio=2.0, max_drawdown_pct=3.0, win_rate=0.65,
            total_trades=20, winning_trades=13,
        )
        reporter.add_monthly_metrics(metrics)

        data = reporter.get_report_data()
        assert data["investor_name"] == "Bob Johnson"
        assert len(data["monthly_metrics"]) == 1
        assert data["monthly_metrics"][0]["return_pct"] == 5.0
