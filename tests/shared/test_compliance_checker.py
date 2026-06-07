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
        violations = ["Violation 1", "Violation 2"]
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

    def test_result_attribute_access(self):
        """Should support normal attribute access."""
        result = ComplianceResult(passes=True, violations=[], warnings=[])
        assert result.passes is True
        assert result.violations == []
        assert result.warnings == []


class TestCheckTrade:
    """Test basic trade validation."""

    def test_valid_long_trade(self):
        """Should approve valid long trade."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100)
        assert result.passes is True
        assert result.violations == []

    def test_valid_short_trade(self):
        """Should approve valid short trade."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="MSFT", action="short", quantity=50)
        assert result.passes is True
        assert result.violations == []

    def test_invalid_quantity_zero(self):
        """Should reject zero quantity."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=0)
        assert result.passes is False
        assert any("positive" in v.lower() for v in result.violations)

    def test_invalid_quantity_negative(self):
        """Should reject negative quantity."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=-100)
        assert result.passes is False
        assert any("positive" in v.lower() for v in result.violations)

    def test_quantity_exceeds_max(self):
        """Should reject quantity over 10000 shares."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=10001)
        assert result.passes is False
        assert any("10000" in v for v in result.violations)

    def test_invalid_symbol_empty(self):
        """Should reject empty symbol."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="", action="long", quantity=100)
        assert result.passes is False
        assert any("symbol" in v.lower() for v in result.violations)

    def test_invalid_symbol_lowercase(self):
        """Should reject lowercase symbol."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="aapl", action="long", quantity=100)
        assert result.passes is False
        assert any("symbol" in v.lower() for v in result.violations)

    def test_invalid_symbol_too_long(self):
        """Should reject symbol longer than 5 chars."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="TOOLONG", action="long", quantity=100)
        assert result.passes is False
        assert any("symbol" in v.lower() for v in result.violations)

    def test_invalid_action(self):
        """Should reject invalid action."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="invalid", quantity=100)
        assert result.passes is False
        assert any("long" in v.lower() or "short" in v.lower() for v in result.violations)

    def test_short_without_price_warning(self):
        """Should warn on short without last_short_price."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="short", quantity=100, last_short_price=None)
        # Should still pass but with warning
        assert result.passes is True
        assert any("short" in w.lower() for w in result.warnings)

    def test_short_with_price_no_warning(self):
        """Should not warn on short with last_short_price."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="short", quantity=100, last_short_price=150.0
        )
        assert result.passes is True
        assert len([w for w in result.warnings if "short" in w.lower()]) == 0


class TestPDTRule:
    """Test Pattern Day Trading (PDT) rule enforcement."""

    def test_zero_day_trades_allowed(self):
        """Should allow trade with 0 day trades."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=0)
        assert result.passes is True
        assert not any("PDT" in v for v in result.violations)

    def test_one_day_trade_allowed(self):
        """Should allow trade with 1 day trade."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=1)
        assert result.passes is True
        assert not any("PDT" in v for v in result.violations)

    def test_two_day_trades_allowed(self):
        """Should allow trade with 2 day trades."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=2)
        assert result.passes is True
        assert not any("PDT" in v for v in result.violations)

    def test_three_day_trades_allowed(self):
        """Should allow trade with 3 day trades."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=3)
        assert result.passes is True
        assert not any("PDT" in v for v in result.violations)

    def test_four_day_trades_blocked(self):
        """Should reject 4th day trade (PDT violation)."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=4)
        assert result.passes is False
        assert any("PDT" in v for v in result.violations)

    def test_five_day_trades_blocked(self):
        """Should reject 5th day trade (PDT violation)."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=5)
        assert result.passes is False
        assert any("PDT" in v for v in result.violations)

    def test_pdt_message_includes_count(self):
        """PDT violation message should include day trade count."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100, day_trades_today=4)
        assert result.passes is False
        assert any("4" in v for v in result.violations)


class TestShortSaleChecks:
    """Test short sale specific validations."""

    def test_short_sale_above_last_price(self):
        """Should allow short at price >= last short price."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="AAPL", quantity=100, current_price=150.0, last_short_price=150.0
        )
        assert result.passes is True
        assert "uptick" not in " ".join(result.violations).lower()

    def test_short_sale_below_last_price_rejected(self):
        """Should reject short at price < last short price (uptick rule)."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="AAPL", quantity=100, current_price=145.0, last_short_price=150.0
        )
        assert result.passes is False
        assert any("uptick" in v.lower() for v in result.violations)

    def test_short_with_1pct_tolerance(self):
        """Should allow short within 1% of last price."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="AAPL", quantity=100, current_price=149.0, last_short_price=150.0
        )
        assert result.passes is True

    def test_short_zero_quantity_rejected(self):
        """Should reject short with zero quantity."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="AAPL", quantity=0, current_price=150.0, last_short_price=150.0
        )
        assert result.passes is False

    def test_short_negative_quantity_rejected(self):
        """Should reject short with negative quantity."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="AAPL", quantity=-100, current_price=150.0, last_short_price=150.0
        )
        assert result.passes is False

    def test_short_invalid_symbol_rejected(self):
        """Should reject short with invalid symbol."""
        checker = ComplianceChecker()
        result = checker.check_short_sale(
            symbol="toolong", quantity=100, current_price=150.0, last_short_price=150.0
        )
        assert result.passes is False


class TestPDTStatus:
    """Test PDT account status checking."""

    def test_margin_account_below_4_trades(self):
        """Margin account with < 4 day trades should be allowed."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=25000, day_trades_count=3)
        assert result.passes is True

    def test_margin_account_4_trades_25k_equity(self):
        """Margin account with 4 trades and $25k equity should be allowed."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=25000, day_trades_count=4)
        assert result.passes is True

    def test_margin_account_4_trades_insufficient_equity(self):
        """Margin account with 4 trades but < $25k equity should fail."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=24999, day_trades_count=4)
        assert result.passes is False
        assert any("25k" in v.lower() or "$25" in v for v in result.violations)

    def test_cash_account_no_pdt_restriction(self):
        """Cash account should not have PDT restrictions."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="cash", equity=5000, day_trades_count=10)
        assert result.passes is True

    def test_invalid_account_type(self):
        """Should reject invalid account type."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="invalid", equity=25000, day_trades_count=0)
        assert result.passes is False

    def test_negative_equity_rejected(self):
        """Should reject negative equity."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=-1000, day_trades_count=0)
        assert result.passes is False

    def test_zero_equity_rejected(self):
        """Should reject zero equity."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=0, day_trades_count=0)
        assert result.passes is False

    def test_negative_day_trades_rejected(self):
        """Should reject negative day trades count."""
        checker = ComplianceChecker()
        result = checker.check_pdt_status(account_type="margin", equity=25000, day_trades_count=-1)
        assert result.passes is False


class TestPositionLimits:
    """Test position size limit warnings."""

    def test_default_position_limit(self):
        """Should accept default 5% position limit."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, position_limit_pct=0.05
        )
        assert result.passes is True

    def test_unusual_position_limit_too_small(self):
        """Should warn on unusually small position limit."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, position_limit_pct=0.001
        )
        # Should still pass but with warning
        assert result.passes is True
        assert any("unusual" in w.lower() for w in result.warnings)

    def test_unusual_position_limit_too_large(self):
        """Should warn on unusually large position limit."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, position_limit_pct=0.75
        )
        # Should still pass but with warning
        assert result.passes is True
        assert any("unusual" in w.lower() for w in result.warnings)

    def test_reasonable_position_limits(self):
        """Should accept reasonable position limits without warning."""
        checker = ComplianceChecker()
        for limit in [0.01, 0.05, 0.10, 0.25, 0.50]:
            result = checker.check_trade(
                symbol="AAPL", action="long", quantity=100, position_limit_pct=limit
            )
            assert result.passes is True
            # None of these should generate position limit warnings
            assert not any("unusual" in w.lower() for w in result.warnings)


class TestMultipleViolations:
    """Test when trade has multiple violations."""

    def test_multiple_violations_collected(self):
        """Should collect all violations in one result."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="invalid",  # Invalid symbol
            action="invalid",  # Invalid action
            quantity=-100,  # Invalid quantity
            day_trades_today=5,  # PDT violation
        )
        assert result.passes is False
        assert len(result.violations) >= 3

    def test_violations_list_not_empty(self):
        """Failed result should have non-empty violations list."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="", action="long", quantity=-1)
        assert result.passes is False
        assert isinstance(result.violations, list)
        assert len(result.violations) > 0

    def test_passes_result_no_violations(self):
        """Passing result should have empty violations list."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=100)
        assert result.passes is True
        assert result.violations == []


class TestBrokerLimits:
    """Test broker-specific limits (reserved for future use)."""

    def test_empty_broker_limits_accepted(self):
        """Should accept empty broker limits dict."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, broker_limits={}
        )
        assert result.passes is True

    def test_none_broker_limits_accepted(self):
        """Should accept None broker limits."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, broker_limits=None
        )
        assert result.passes is True

    def test_broker_limits_passed_through(self):
        """Should handle broker limits without error (not implemented yet)."""
        checker = ComplianceChecker()
        broker_limits = {"max_single_order": 5000, "min_notional": 100}
        result = checker.check_trade(
            symbol="AAPL", action="long", quantity=100, broker_limits=broker_limits
        )
        # Should not crash; these limits not enforced yet
        assert isinstance(result, ComplianceResult)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_exactly_10000_shares_allowed(self):
        """Should allow exactly 10000 shares."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=10000)
        assert result.passes is True

    def test_fractional_quantity_allowed(self):
        """Should allow fractional shares."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=10.5)
        assert result.passes is True

    def test_very_small_fractional_allowed(self):
        """Should allow very small fractional quantities."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="AAPL", action="long", quantity=0.001)
        assert result.passes is True

    def test_five_char_symbol_allowed(self):
        """Should allow 5-character symbols."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="ABCDE", action="long", quantity=100)
        assert result.passes is True

    def test_single_char_symbol_allowed(self):
        """Should allow 1-character symbols."""
        checker = ComplianceChecker()
        result = checker.check_trade(symbol="F", action="long", quantity=100)
        assert result.passes is True

    def test_all_valid_parameters(self):
        """Should pass with all valid parameters."""
        checker = ComplianceChecker()
        result = checker.check_trade(
            symbol="AAPL",
            action="long",
            quantity=100,
            position_limit_pct=0.05,
            day_trades_today=2,
            last_short_price=None,
            broker_limits={},
        )
        assert result.passes is True
        assert result.violations == []
