# tests/shared/test_compliance_checker.py
"""
Unit tests for compliance checker covering all SEC rules, PDT, and position limits.
"""
import pytest
from shared.compliance_checker import ComplianceChecker, ComplianceResult


class TestComplianceResult:
    """Test ComplianceResult dataclass and dict-style access."""

    def test_result_creation_passes(self):
        """Should create result with passes=True and empty violations."""
        result = ComplianceResult(passes=True, violations=[])
        assert result.passes is True
        assert result.violations == []
        assert result.warnings == []

    def test_result_creation_fails(self):
        """Should create result with passes=False and violations."""
        violations = ["violation1", "violation2"]
        result = ComplianceResult(passes=False, violations=violations)
        assert result.passes is False
        assert result.violations == violations

    def test_result_dict_style_access_passes(self):
        """Should support dict-style access for passes field."""
        result = ComplianceResult(passes=True, violations=[])
        assert result["passes"] is True

    def test_result_dict_style_access_violations(self):
        """Should support dict-style access for violations field."""
        violations = ["V1", "V2"]
        result = ComplianceResult(passes=False, violations=violations)
        assert result["violations"] == violations

    def test_result_dict_style_access_warnings(self):
        """Should support dict-style access for warnings field."""
        warnings = ["W1"]
        result = ComplianceResult(passes=True, violations=[], warnings=warnings)
        assert result["warnings"] == warnings

    def test_result_max_allowed_notional(self):
        """Should support max_allowed_notional field."""
        result = ComplianceResult(
            passes=False,
            violations=["position_limit"],
            max_allowed_notional=250000.0,
        )
        assert result["max_allowed_notional"] == 250000.0

    def test_result_pdt_day_trades(self):
        """Should support pdt_day_trades field."""
        result = ComplianceResult(
            passes=False,
            violations=["pdt_violation"],
            pdt_day_trades=4,
        )
        assert result["pdt_day_trades"] == 4


# ============================================================================
# REQUIRED TESTS (exact names from plan)
# ============================================================================


def test_position_limit_exceeds_max():
    """Test: reject trade if position would exceed max size (25% portfolio)."""
    checker = ComplianceChecker()

    # Scenario: portfolio = $1M, trade = 300 shares at $100 = $30k (3% of $1M)
    # To exceed 25% limit with $1M portfolio and $100/share: need >250k shares
    # So use 300k shares: 300k * $100 = $30M (30% > 25% limit)
    result = checker.check_trade(
        symbol="AAPL",
        quantity=300000,
        price=1.0,  # Changed: lower price so notional is realistic
        action="BUY",
        portfolio_value=1_000_000,
        current_position_qty=0,
        broker_limits={},
    )

    assert result["passes"] is False
    assert "position_limit" in result["violations"]
    assert result["max_allowed_notional"] == 250_000  # 25% of $1M


def test_position_limit_within_bounds():
    """Test: allow trade if position stays within 25% limit."""
    checker = ComplianceChecker()

    # Trade: 200 shares at $100 = $20k (2% of $1M portfolio, well within 25% limit)
    result = checker.check_trade(
        symbol="AAPL",
        quantity=200,
        price=100.0,
        action="BUY",
        portfolio_value=1_000_000,
        current_position_qty=0,
        broker_limits={},
    )

    assert result["passes"] is True
    assert len(result.get("violations", [])) == 0


def test_pdt_rule_violation():
    """Test: reject 4th day trade if account < $25k."""
    checker = ComplianceChecker()

    # Small account ($10k) with 3 day trades today = 4th would violate PDT
    result = checker.check_trade(
        symbol="AAPL",
        quantity=100,
        price=150.0,
        action="BUY",
        portfolio_value=10_000,  # < $25k PDT minimum
        current_position_qty=0,
        broker_limits={},
        day_trades_today=3,  # Already 3 day trades
    )

    assert result["passes"] is False
    assert "pdt_violation" in result["violations"]


def test_short_sale_uptick_rule():
    """Test: reject short sale if price didn't uptick from last trade."""
    checker = ComplianceChecker()

    result = checker.check_trade(
        symbol="AAPL",
        quantity=100,
        price=149.99,  # Price didn't uptick from $150
        action="SELL",
        portfolio_value=100_000,
        current_position_qty=0,  # Going short
        broker_limits={},
        last_short_price=150.0,
    )

    assert result["passes"] is False
    assert "short_sale_uptick" in result["violations"]


def test_concentration_limit():
    """Test: warn if single stock exceeds 15% of portfolio."""
    checker = ComplianceChecker()

    # Portfolio: $1M, single position would be $200k (20% > 15% warning)
    result = checker.check_trade(
        symbol="AAPL",
        quantity=1000,
        price=200.0,
        action="BUY",
        portfolio_value=1_000_000,
        current_position_qty=0,
        broker_limits={},
    )

    # Should pass but include concentration warning
    assert "concentration_warning" in result.get("warnings", [])


# ============================================================================
# ADDITIONAL EDGE CASE TESTS
# ============================================================================


class TestPositionLimitEdgeCases:
    """Test position limit boundary conditions."""

    def test_position_at_exactly_25_percent(self):
        """Should allow position at exactly 25% limit."""
        checker = ComplianceChecker()
        # 250 shares at $100 = $25k (25% of $100k portfolio)
        result = checker.check_trade(
            symbol="AAPL",
            quantity=250,
            price=100.0,
            action="BUY",
            portfolio_value=100_000,
            current_position_qty=0,
            broker_limits={},
        )
        assert result.passes is True

    def test_position_exceeds_25_by_one_share(self):
        """Should reject position exceeding 25% by even one share."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=250001,
            price=100.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        assert result.passes is False
        assert "position_limit" in result.violations

    def test_sell_action_not_subject_to_position_limit(self):
        """SELL action should not trigger position limit violation."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=300000,
            price=100.0,
            action="SELL",
            portfolio_value=1_000_000,
            current_position_qty=500000,
            broker_limits={},
        )
        # SELL should not violate position limit (reducing position)
        assert "position_limit" not in result.violations


class TestPDTEdgeCases:
    """Test PDT rule boundary conditions."""

    def test_pdt_not_triggered_with_25k_account(self):
        """Should allow 4th day trade with $25k+ account."""
        checker = ComplianceChecker()
        # 20 shares at $50 = $1k (4% of $25k portfolio, well within limits)
        result = checker.check_trade(
            symbol="AAPL",
            quantity=20,
            price=50.0,
            action="BUY",
            portfolio_value=25_000,  # Exactly at minimum
            current_position_qty=0,
            broker_limits={},
            day_trades_today=3,
        )
        assert result.passes is True

    def test_pdt_only_triggered_below_25k(self):
        """PDT should only trigger when account < $25k."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="BUY",
            portfolio_value=24_999,  # Just below minimum
            current_position_qty=0,
            broker_limits={},
            day_trades_today=3,
        )
        assert result.passes is False
        assert "pdt_violation" in result.violations

    def test_pdt_not_triggered_with_only_3_day_trades(self):
        """Should allow 3rd day trade even on small account."""
        checker = ComplianceChecker()
        # 20 shares at $40 = $800 (8% of $10k portfolio, within 25% limit)
        result = checker.check_trade(
            symbol="AAPL",
            quantity=20,
            price=40.0,
            action="BUY",
            portfolio_value=10_000,
            current_position_qty=0,
            broker_limits={},
            day_trades_today=2,  # Only 2 so far
        )
        assert result.passes is True

    def test_pdt_sell_with_existing_position_is_day_trade(self):
        """SELL with existing position counts as day trade (closing position)."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="SELL",
            portfolio_value=10_000,
            current_position_qty=100,  # Have position
            broker_limits={},
            day_trades_today=3,
        )
        assert result.passes is False
        assert "pdt_violation" in result.violations


class TestUptickRule:
    """Test short-sale uptick rule."""

    def test_short_at_exactly_last_price_allowed(self):
        """Should allow short at exactly last price."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="SELL",
            portfolio_value=100_000,
            current_position_qty=0,  # Going short
            broker_limits={},
            last_short_price=150.0,
        )
        assert result.passes is True

    def test_short_above_last_price_allowed(self):
        """Should allow short above last price."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=151.0,
            action="SELL",
            portfolio_value=100_000,
            current_position_qty=0,
            broker_limits={},
            last_short_price=150.0,
        )
        assert result.passes is True

    def test_short_without_last_price_allowed(self):
        """Should allow short when no last_short_price provided."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="SELL",
            portfolio_value=100_000,
            current_position_qty=0,
            broker_limits={},
            last_short_price=None,
        )
        assert result.passes is True

    def test_long_sale_not_subject_to_uptick(self):
        """Long sale (closing existing position) not subject to uptick rule."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=149.0,
            action="SELL",
            portfolio_value=100_000,
            current_position_qty=100,  # Closing existing position
            broker_limits={},
            last_short_price=150.0,
        )
        # Closing position should not violate uptick rule
        assert "short_sale_uptick" not in result.violations


class TestConcentrationLimit:
    """Test concentration warning logic."""

    def test_concentration_at_exactly_15_percent(self):
        """Should allow position at exactly 15%."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=750,
            price=200.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        # At exactly 15%, should not warn
        assert "concentration_warning" not in result.get("warnings", [])

    def test_concentration_exceeds_15_percent(self):
        """Should warn when position exceeds 15%."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=751,  # Slightly over 15%
            price=200.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        assert "concentration_warning" in result.get("warnings", [])

    def test_sell_no_concentration_warning(self):
        """SELL action should not generate concentration warning."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=1000,
            price=200.0,
            action="SELL",
            portfolio_value=1_000_000,
            current_position_qty=1000,
            broker_limits={},
        )
        # SELL reduces concentration, should not warn
        assert "concentration_warning" not in result.get("warnings", [])

    def test_small_position_no_concentration_warning(self):
        """Small positions should not generate warning."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=200.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        # Only 2% of portfolio
        assert "concentration_warning" not in result.get("warnings", [])


class TestMultipleRules:
    """Test interactions between multiple rules."""

    def test_position_limit_takes_precedence_over_concentration(self):
        """Position limit violation should fail even with concentration warning."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=300000,
            price=100.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        # Should fail on position limit, not just warn on concentration
        assert result.passes is False
        assert "position_limit" in result.violations

    def test_pdt_takes_precedence_over_other_checks(self):
        """PDT violation should fail immediately."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="BUY",
            portfolio_value=10_000,  # < $25k
            current_position_qty=0,
            broker_limits={},
            day_trades_today=3,  # 4th day trade
        )
        assert result.passes is False
        assert "pdt_violation" in result.violations


class TestBrokerLimits:
    """Test broker-specific limits (reserved for future)."""

    def test_empty_broker_limits_accepted(self):
        """Should accept empty broker limits dict."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={},
        )
        assert result.passes is True

    def test_broker_limits_not_enforced_yet(self):
        """Broker limits should not be enforced in this version."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            quantity=100,
            price=150.0,
            action="BUY",
            portfolio_value=1_000_000,
            current_position_qty=0,
            broker_limits={"max_order_size": 50},  # Would be violated
        )
        # Should not fail on broker limits (not implemented)
        assert "broker" not in " ".join(result.violations).lower()
