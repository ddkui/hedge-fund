"""Tax report generation with Schedule D export."""
import pytest
from datetime import datetime, timedelta
from shared.tax_calculator import TaxCalculator
from shared.tax_reporter import TaxReporter, TaxGain


def test_schedule_d_short_term_gains():
    """Test: Schedule D report includes short-term gains (Part I)."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 shares on Jan 1, 2026
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell 100 shares on Jun 15, 2026 (168 days, < 365 = short-term)
    calc.record_sale("AAPL", 100, 120.0, datetime(2026, 6, 15))

    # Create reporter
    reporter = TaxReporter(calc)
    schedule_d = reporter.generate_schedule_d()

    # Verify short-term gains are in Part I
    assert "part_i_short_term" in schedule_d
    assert len(schedule_d["part_i_short_term"]) == 1

    # Verify gain details
    gain = schedule_d["part_i_short_term"][0]
    assert gain.symbol == "AAPL"
    assert gain.quantity == 100
    assert gain.proceeds == 12000.0  # 100 * 120
    assert gain.cost_basis == 10000.0  # 100 * 100
    assert gain.gain == 2000.0  # proceeds - cost


def test_schedule_d_long_term_gains():
    """Test: Schedule D report includes long-term gains (Part II)."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 shares on Jun 1, 2024
    calc.add_lot("MSFT", 100, 250.0, datetime(2024, 6, 1))

    # Sell 100 shares on Jun 15, 2026 (745 days, >= 365 = long-term)
    calc.record_sale("MSFT", 100, 320.0, datetime(2026, 6, 15))

    # Create reporter
    reporter = TaxReporter(calc)
    schedule_d = reporter.generate_schedule_d()

    # Verify long-term gains are in Part II
    assert "part_ii_long_term" in schedule_d
    assert len(schedule_d["part_ii_long_term"]) == 1

    # Verify gain details
    gain = schedule_d["part_ii_long_term"][0]
    assert gain.symbol == "MSFT"
    assert gain.quantity == 100
    assert gain.proceeds == 32000.0  # 100 * 320
    assert gain.cost_basis == 25000.0  # 100 * 250
    assert gain.gain == 7000.0  # proceeds - cost


def test_schedule_d_mixed_gains():
    """Test: Schedule D separates short-term and long-term gains."""
    calc = TaxCalculator(method="FIFO")

    # Short-term gain
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))
    calc.record_sale("AAPL", 100, 120.0, datetime(2026, 6, 15))

    # Long-term gain
    calc.add_lot("MSFT", 100, 250.0, datetime(2024, 6, 1))
    calc.record_sale("MSFT", 100, 320.0, datetime(2026, 6, 15))

    # Create reporter
    reporter = TaxReporter(calc)
    schedule_d = reporter.generate_schedule_d()

    # Verify both parts exist
    assert len(schedule_d["part_i_short_term"]) == 1
    assert len(schedule_d["part_ii_long_term"]) == 1

    # Verify totals
    assert schedule_d["part_i_total_gain"] == 2000.0
    assert schedule_d["part_ii_total_gain"] == 7000.0
    assert schedule_d["total_gain"] == 9000.0


def test_schedule_d_losses():
    """Test: Schedule D includes losses (negative gains)."""
    calc = TaxCalculator(method="FIFO")

    # Short-term loss
    calc.add_lot("AAPL", 100, 150.0, datetime(2026, 1, 1))
    calc.record_sale("AAPL", 100, 100.0, datetime(2026, 6, 15))

    # Long-term loss
    calc.add_lot("MSFT", 100, 350.0, datetime(2024, 6, 1))
    calc.record_sale("MSFT", 100, 300.0, datetime(2026, 6, 15))

    # Create reporter
    reporter = TaxReporter(calc)
    schedule_d = reporter.generate_schedule_d()

    # Verify losses
    st_loss = schedule_d["part_i_short_term"][0]
    lt_loss = schedule_d["part_ii_long_term"][0]

    assert st_loss.gain == -5000.0  # 10000 - 15000
    assert lt_loss.gain == -5000.0  # 30000 - 35000


def test_export_schedule_d_csv():
    """Test: Schedule D exports as CSV format."""
    calc = TaxCalculator(method="FIFO")

    # Add a short-term gain
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))
    calc.record_sale("AAPL", 100, 120.0, datetime(2026, 6, 15))

    # Add a long-term gain
    calc.add_lot("MSFT", 100, 250.0, datetime(2024, 6, 1))
    calc.record_sale("MSFT", 100, 320.0, datetime(2026, 6, 15))

    reporter = TaxReporter(calc)
    csv_output = reporter.export_schedule_d_csv()

    # Verify CSV structure
    lines = csv_output.strip().split("\n")

    # Should have header + 4 section headers + 2 gains + 2 totals
    assert "SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN" in lines[0]
    assert "Part I - Short-Term Capital Gains" in csv_output
    assert "Part II - Long-Term Capital Gains" in csv_output

    # Verify data rows
    assert "AAPL" in csv_output
    assert "MSFT" in csv_output


def test_schedule_d_empty():
    """Test: Empty calculator returns empty Schedule D."""
    calc = TaxCalculator(method="FIFO")
    reporter = TaxReporter(calc)
    schedule_d = reporter.generate_schedule_d()

    assert schedule_d["part_i_short_term"] == []
    assert schedule_d["part_ii_long_term"] == []
    assert schedule_d["part_i_total_gain"] == 0.0
    assert schedule_d["part_ii_total_gain"] == 0.0
    assert schedule_d["total_gain"] == 0.0


def test_tax_gain_dataclass():
    """Test: TaxGain dataclass stores gain information."""
    gain = TaxGain(
        symbol="AAPL",
        quantity=100,
        cost_basis=10000.0,
        proceeds=12000.0,
        gain=2000.0,
        holding_period="short_term"
    )

    assert gain.symbol == "AAPL"
    assert gain.quantity == 100
    assert gain.cost_basis == 10000.0
    assert gain.proceeds == 12000.0
    assert gain.gain == 2000.0
    assert gain.holding_period == "short_term"
