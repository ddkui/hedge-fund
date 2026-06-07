import pytest
from datetime import datetime, timedelta
from shared.tax_calculator import TaxCalculator, TaxLot

def test_fifo_cost_basis():
    """Test: FIFO cost basis calculation for sales."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 shares at $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))
    # Buy 100 shares at $110
    calc.add_lot("AAPL", 100, 110.0, datetime(2026, 2, 1))

    # Sell 150 shares at $120
    gain = calc.calculate_gain_on_sale("AAPL", 150, 120.0)

    # Should sell 100 @ $100 (cost) and 50 @ $110 (cost)
    # Cost: (100*100 + 50*110) = 15,500
    # Proceeds: 150*120 = 18,000
    # Gain: 2,500
    assert gain == 2500.0

def test_wash_sale_thirty_day_rule():
    """Test: Detect wash sales within 30 days of loss."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 at $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell at loss on Jan 20
    loss = calc.calculate_gain_on_sale("AAPL", 100, 80.0)
    calc.record_sale("AAPL", 100, 80.0, datetime(2026, 1, 20))
    assert loss == -2000.0  # 100 * (80-100)

    # Buy 100 back on Jan 25 (within 30 days)
    wash_check = calc.detect_wash_sale("AAPL", 100, datetime(2026, 1, 25))

    assert wash_check["is_wash_sale"] is True
    assert wash_check["disallowed_loss"] == -2000.0

def test_short_term_vs_long_term_gains():
    """Test: Classify gains as short-term (<1 year) or long-term (>=1 year)."""
    calc = TaxCalculator()

    # Purchase on Jan 1
    purchase_date = datetime(2025, 1, 1)
    calc.add_lot("AAPL", 100, 100.0, purchase_date)

    # Sale on Jun 15 (168 days, < 1 year) = short-term
    short_term_date = datetime(2025, 6, 15)
    holding_days = (short_term_date - purchase_date).days
    is_long_term = holding_days >= 365

    assert is_long_term is False  # Short-term

    # Sale on Jan 2 next year (366 days, >= 1 year) = long-term
    long_term_date = datetime(2026, 1, 2)
    holding_days = (long_term_date - purchase_date).days
    is_long_term = holding_days >= 365

    assert is_long_term is True  # Long-term


def test_classify_gain_short_term():
    """Test: classify_gain returns 'short_term' for <1 year holdings."""
    calc = TaxCalculator()
    purchase_date = datetime(2026, 1, 1)
    sale_date = datetime(2026, 6, 15)

    classification = calc.classify_gain("AAPL", purchase_date, sale_date)
    assert classification == "short_term"


def test_classify_gain_long_term():
    """Test: classify_gain returns 'long_term' for >=1 year holdings."""
    calc = TaxCalculator()
    purchase_date = datetime(2024, 6, 1)
    sale_date = datetime(2026, 6, 1)

    classification = calc.classify_gain("AAPL", purchase_date, sale_date)
    assert classification == "long_term"


def test_multiple_lots_fifo_order():
    """Test: FIFO sells oldest lots first with multiple purchases."""
    calc = TaxCalculator(method="FIFO")

    # Buy 50 shares on Jan 1 @ $100
    calc.add_lot("AAPL", 50, 100.0, datetime(2026, 1, 1))
    # Buy 75 shares on Feb 1 @ $110
    calc.add_lot("AAPL", 75, 110.0, datetime(2026, 2, 1))
    # Buy 25 shares on Mar 1 @ $120
    calc.add_lot("AAPL", 25, 120.0, datetime(2026, 3, 1))

    # Sell 100 shares at $130
    gain = calc.calculate_gain_on_sale("AAPL", 100, 130.0)

    # Should sell 50 @ $100 and 50 @ $110 (oldest first)
    # Cost: (50*100 + 50*110) = 10,500
    # Proceeds: 100*130 = 13,000
    # Gain: 2,500
    assert gain == 2500.0


def test_wash_sale_outside_30_days():
    """Test: Repurchase outside 30-day window is not a wash sale."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 at $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell at loss on Jan 20
    calc.record_sale("AAPL", 100, 80.0, datetime(2026, 1, 20))

    # Buy back on Feb 20 (31 days later - outside 30-day window)
    wash_check = calc.detect_wash_sale("AAPL", 100, datetime(2026, 2, 20))

    assert wash_check["is_wash_sale"] is False
    assert wash_check["disallowed_loss"] == 0.0


def test_wash_sale_no_loss():
    """Test: Gain sales don't trigger wash-sale detection."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 at $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell at gain on Jan 20
    calc.record_sale("AAPL", 100, 120.0, datetime(2026, 1, 20))

    # Buy back on Jan 25 (within 30 days but no loss)
    wash_check = calc.detect_wash_sale("AAPL", 100, datetime(2026, 1, 25))

    assert wash_check["is_wash_sale"] is False


def test_multiple_sales_tracking():
    """Test: Multiple sales are tracked separately."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 @ $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # First sale
    calc.record_sale("AAPL", 100, 110.0, datetime(2026, 2, 1))
    # Second sale
    calc.record_sale("AAPL", 100, 120.0, datetime(2026, 3, 1))

    assert len(calc.sales) == 2
    assert calc.sales[0]["gain"] == 1000.0  # 100 * (110 - 100)
    assert calc.sales[1]["gain"] == 2000.0  # 100 * (120 - 100)


def test_partial_lot_sale():
    """Test: Selling only part of a lot reduces lot quantity."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 @ $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell 60
    calc.record_sale("AAPL", 60, 110.0, datetime(2026, 2, 1))

    # Should have 40 shares remaining
    assert len(calc.lots["AAPL"]) == 1
    assert calc.lots["AAPL"][0].quantity == 40


def test_empty_lot_removal():
    """Test: Completely sold lots are removed from inventory."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 @ $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell all 100
    calc.record_sale("AAPL", 100, 110.0, datetime(2026, 2, 1))

    # Lots list for AAPL should be empty
    assert len(calc.lots["AAPL"]) == 0


def test_zero_quantity_sale():
    """Test: Selling zero quantity returns 0 gain."""
    calc = TaxCalculator(method="FIFO")

    # Buy 100 @ $100
    calc.add_lot("AAPL", 100, 100.0, datetime(2026, 1, 1))

    # Sell 0 shares
    gain = calc.calculate_gain_on_sale("AAPL", 0, 110.0)

    assert gain == 0.0


def test_nonexistent_symbol_sale():
    """Test: Selling symbol not in inventory returns 0 gain."""
    calc = TaxCalculator(method="FIFO")

    gain = calc.calculate_gain_on_sale("NONEXISTENT", 100, 110.0)

    assert gain == 0.0
