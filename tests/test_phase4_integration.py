"""Phase 4 Integration tests: Compliance, Tax Reporting, 13F Filing, Audit Export."""
import pytest
from datetime import datetime, timedelta, timezone
from shared.compliance_checker import ComplianceChecker
from shared.tax_calculator import TaxCalculator
from shared.tax_reporter import TaxReporter
from shared.form13f_generator import Form13FGenerator
from shared.audit_exporter import AuditExporter, TradeAuditRecord


class TestFullComplianceAndReportingFlow:
    """Test: Full E2E flow covering all Phase 4 features."""

    def test_full_compliance_and_reporting_flow(self):
        """
        Full E2E integration test:
        1. Compliance check (✓)
        2. Tax tracking (add_lot + record_sale) (✓)
        3. Tax reporting (generate_schedule_d) (✓)
        4. 13F filing (add_position + generate_filing) (✓)
        5. Audit export (add_record + export_csv) (✓)
        """

        # ===== PHASE 4.1: COMPLIANCE CHECK =====
        compliance = ComplianceChecker(max_position_pct=0.25, pdt_min_account_value=25000)

        # Check trade that should pass
        result = compliance.check_trade(
            symbol="AAPL",
            quantity=10,
            price=150.0,
            action="BUY",
            portfolio_value=100000.0,
            current_position_qty=0,
            broker_limits={},
            day_trades_today=0,
        )
        assert result.passes is True, "Valid trade should pass compliance"
        assert len(result.violations) == 0, "Should have no violations"

        # ===== PHASE 4.2: TAX TRACKING =====
        tax_calc = TaxCalculator(method="FIFO")

        # Add tax lot (BUY at $100)
        purchase_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
        tax_calc.add_lot(
            symbol="TSLA",
            quantity=100,
            price=100.0,
            purchase_date=purchase_date,
        )
        assert "TSLA" in tax_calc.lots, "Tax lot should be added"

        # Record sale (SELL at $120)
        sale_date = datetime(2024, 6, 15, tzinfo=timezone.utc)
        tax_calc.record_sale(
            symbol="TSLA",
            quantity=100,
            sale_price=120.0,
            sale_date=sale_date,
        )
        assert len(tax_calc.sales) == 1, "Sale should be recorded"
        assert tax_calc.sales[0]["gain"] == 2000.0, "Gain should be $2000 (100 @ $120 - cost basis)"

        # ===== PHASE 4.3: TAX REPORTING =====
        tax_reporter = TaxReporter(tax_calc)
        schedule_d = tax_reporter.generate_schedule_d()

        assert "part_i_short_term" in schedule_d, "Schedule D should have Part I"
        assert "part_ii_long_term" in schedule_d, "Schedule D should have Part II"
        assert schedule_d["total_gain"] == 2000.0, "Total gain should be $2000"

        # Export Schedule D as CSV
        csv_output = tax_reporter.export_schedule_d_csv()
        assert "TSLA" in csv_output, "CSV should contain TSLA"
        assert "Part I" in csv_output, "CSV should have Part I section"
        assert "Part II" in csv_output, "CSV should have Part II section"

        # ===== PHASE 4.4: 13F FILING =====
        form13f = Form13FGenerator(
            cik="0001234567",
            fund_name="Test Fund",
            fiscal_quarter="Q2",
            fiscal_year=2024,
        )

        # Add positions
        form13f.add_position(
            symbol="AAPL",
            quantity=100,
            market_value=15000.0,
            price_per_share=150.0,
            cusip="037833100",
        )
        form13f.add_position(
            symbol="MSFT",
            quantity=50,
            market_value=18000.0,
            price_per_share=360.0,
            cusip="594918104",
        )

        # Generate filing
        filing = form13f.generate_filing()
        assert filing["cik"] == "0001234567", "CIK should match"
        assert filing["position_count"] == 2, "Should have 2 positions"
        assert filing["total_value"] == 33000.0, "Total value should be $33k"

        # Export as CSV
        csv_filing = form13f.export_csv()
        assert "AAPL" in csv_filing, "CSV should contain AAPL"
        assert "MSFT" in csv_filing, "CSV should contain MSFT"

        # ===== PHASE 4.5: AUDIT TRAIL EXPORT =====
        audit = AuditExporter()

        # Add trade records
        record1 = TradeAuditRecord(
            trade_id="TRD001",
            symbol="AAPL",
            action="BUY",
            quantity=10,
            price=150.0,
            executed_at=datetime.now(timezone.utc),
            agent_signals=["technical:bullish:0.85", "momentum:bullish:0.75"],
            consensus_score=0.80,
            risk_check_passed=True,
            cio_approval_required=False,
            execution_notes="Automated execution",
        )
        audit.add_record(record1)

        record2 = TradeAuditRecord(
            trade_id="TRD002",
            symbol="MSFT",
            action="SELL",
            quantity=5,
            price=360.0,
            executed_at=datetime.now(timezone.utc),
            agent_signals=["technical:bearish:0.70"],
            consensus_score=0.70,
            risk_check_passed=True,
            cio_approval_required=False,
            execution_notes="Profit taking",
        )
        audit.add_record(record2)

        # Export audit trail as CSV
        csv_audit = audit.export_csv()
        assert "TRD001" in csv_audit, "CSV should contain TRD001"
        assert "TRD002" in csv_audit, "CSV should contain TRD002"
        assert "AAPL" in csv_audit, "CSV should contain AAPL"
        assert "MSFT" in csv_audit, "CSV should contain MSFT"

        # Export audit trail as PDF
        pdf_bytes = audit.export_pdf()
        assert len(pdf_bytes) > 0, "PDF should be generated"
        assert pdf_bytes[:4] == b"%PDF", "PDF should have correct magic bytes"

        # ===== VERIFY FULL FLOW COMPLETION =====
        assert result.passes, "Compliance passed"
        assert tax_calc.sales, "Taxes tracked"
        assert schedule_d["total_gain"] > 0, "Tax reporting generated"
        assert filing["position_count"] > 0, "13F filing generated"
        assert len(csv_audit) > 0, "Audit trail exported"


class TestWashSaleDisallowsLoss:
    """Test: Wash sale detection prevents loss deduction."""

    def test_wash_sale_disallows_loss(self):
        """
        Scenario:
        1. Buy at $100 (1/1/2024)
        2. Sell at $80 (2/1/2024) - loss of $2000
        3. Repurchase at $85 (2/15/2024) - within 30 days
        4. Verify wash sale detected and loss disallowed
        """
        tax_calc = TaxCalculator(method="FIFO")

        # Step 1: BUY at $100
        buy_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        tax_calc.add_lot(
            symbol="XYZ",
            quantity=100,
            price=100.0,
            purchase_date=buy_date,
        )

        # Step 2: SELL at $80 (loss)
        sell_date = datetime(2024, 2, 1, tzinfo=timezone.utc)
        tax_calc.record_sale(
            symbol="XYZ",
            quantity=100,
            sale_price=80.0,
            sale_date=sell_date,
        )

        # Verify loss was recorded
        assert len(tax_calc.sales) == 1
        sale = tax_calc.sales[0]
        assert sale["gain"] == -2000.0, "Loss should be -$2000"
        assert sale["sale_date"] == sell_date

        # Step 3: REPURCHASE within 30 days (wash sale!)
        repurchase_date = datetime(2024, 2, 15, tzinfo=timezone.utc)
        wash_check = tax_calc.detect_wash_sale(
            symbol="XYZ",
            quantity=100,
            repurchase_date=repurchase_date,
        )

        # Step 4: VERIFY wash sale detected
        assert wash_check.is_wash_sale is True, "Wash sale should be detected"
        assert wash_check.disallowed_loss == -2000.0, "Disallowed loss should be $2000"
        assert "30 days" in wash_check.reason, "Reason should mention 30-day period"


class TestPDTRuleBlocksFourthDayTrade:
    """Test: PDT rule prevents 4th day trade on small accounts."""

    def test_pdt_rule_blocks_fourth_day_trade(self):
        """
        Scenario:
        1. Small account ($10k, below $25k PDT threshold)
        2. Already executed 3 day trades
        3. 4th day trade should be BLOCKED
        """
        compliance = ComplianceChecker(
            max_position_pct=0.25,
            pdt_min_account_value=25000.0,
        )

        # Setup: Small account ($10k), 3 day trades already done
        portfolio_value = 10000.0
        day_trades_done = 3

        # Attempt: 4th day trade (buy to open new position)
        result = compliance.check_trade(
            symbol="AAPL",
            quantity=10,
            price=150.0,
            action="BUY",  # Opening new position = 4th day trade
            portfolio_value=portfolio_value,
            current_position_qty=0,  # No existing position
            broker_limits={},
            day_trades_today=day_trades_done,
        )

        # Verify: 4th day trade blocked
        assert result.passes is False, "4th day trade should be blocked"
        assert "pdt_violation" in result.violations, "Should have PDT violation"
        assert result.pdt_day_trades == 4, "Should show 4 day trades"

        # Sanity check: With $25k account, same trade should PASS
        result_large_account = compliance.check_trade(
            symbol="AAPL",
            quantity=10,
            price=150.0,
            action="BUY",
            portfolio_value=25000.0,  # Meets PDT minimum
            current_position_qty=0,
            broker_limits={},
            day_trades_today=day_trades_done,
        )
        assert result_large_account.passes is True, "Large account should allow 4th day trade"
