# tests/shared/test_form13f_generator.py
import pytest
from datetime import datetime
from shared.form13f_generator import Form13FGenerator, Form13FPosition

def test_aggregate_holdings_into_positions():
    """Test: Aggregate multiple purchases of same stock into single position."""
    generator = Form13FGenerator(
        cik="0001234567",
        fund_name="Hedge Fund AI",
        fiscal_quarter="Q1",
        fiscal_year=2026,
    )

    # Add holdings from trades
    generator.add_position(
        symbol="AAPL",
        quantity=1000,
        market_value=150000,
        price_per_share=150.0,
        cusip="037833100",
    )

    generator.add_position(
        symbol="MSFT",
        quantity=500,
        market_value=160000,
        price_per_share=320.0,
        cusip="594918104",
    )

    positions = generator.get_positions()

    assert len(positions) == 2
    # Positions are sorted by market value descending, so MSFT (160k) comes first
    assert positions[0].symbol == "MSFT"
    assert positions[0].market_value == 160000
    assert positions[1].symbol == "AAPL"
    assert positions[1].quantity == 1000
    assert positions[1].market_value == 150000

def test_13f_format_compliance():
    """Test: Generate 13F format matching SEC requirements."""
    generator = Form13FGenerator(
        cik="0001234567",
        fund_name="Hedge Fund AI",
        fiscal_quarter="Q1",
        fiscal_year=2026,
    )

    generator.add_position(
        symbol="AAPL",
        quantity=1000,
        market_value=150000,
        price_per_share=150.0,
        cusip="037833100",
    )

    filing = generator.generate_filing()

    assert filing["cik"] == "0001234567"
    assert filing["fund_name"] == "Hedge Fund AI"
    assert filing["period_ended"] == "2026-03-31"  # Q1 ends March 31
    assert len(filing["positions"]) == 1
    assert filing["total_value"] == 150000

def test_csv_export_format():
    """Test: Export 13F positions as CSV."""
    generator = Form13FGenerator(
        cik="0001234567",
        fund_name="Hedge Fund AI",
        fiscal_quarter="Q1",
        fiscal_year=2026,
    )

    generator.add_position(
        symbol="AAPL",
        quantity=1000,
        market_value=150000,
        price_per_share=150.0,
        cusip="037833100",
    )

    csv = generator.export_csv()

    assert "CUSIP,SYMBOL,QUANTITY" in csv
    assert "037833100,AAPL,1000" in csv

def test_aggregate_same_symbol():
    """Test: Adding same symbol twice aggregates quantities and values."""
    generator = Form13FGenerator(
        cik="0001234567",
        fund_name="Hedge Fund AI",
        fiscal_quarter="Q1",
        fiscal_year=2026,
    )

    # First purchase of AAPL
    generator.add_position(
        symbol="AAPL",
        quantity=500,
        market_value=75000,
        price_per_share=150.0,
        cusip="037833100",
    )

    # Second purchase of AAPL (aggregates)
    generator.add_position(
        symbol="AAPL",
        quantity=500,
        market_value=75000,
        price_per_share=150.0,
        cusip="037833100",
    )

    positions = generator.get_positions()
    assert len(positions) == 1
    assert positions[0].quantity == 1000
    assert positions[0].market_value == 150000

def test_positions_sorted_by_market_value():
    """Test: Positions sorted by market value descending."""
    generator = Form13FGenerator(
        cik="0001234567",
        fund_name="Hedge Fund AI",
        fiscal_quarter="Q2",
        fiscal_year=2026,
    )

    # Add positions in arbitrary order
    generator.add_position("MSFT", 500, 160000, 320.0, "594918104")
    generator.add_position("AAPL", 1000, 150000, 150.0, "037833100")
    generator.add_position("GOOGL", 200, 200000, 1000.0, "02079K305")

    positions = generator.get_positions()

    # Should be sorted by market_value descending
    assert positions[0].symbol == "GOOGL"
    assert positions[0].market_value == 200000
    assert positions[1].symbol == "MSFT"
    assert positions[1].market_value == 160000
    assert positions[2].symbol == "AAPL"
    assert positions[2].market_value == 150000

def test_period_ended_all_quarters():
    """Test: Period ended date correct for all quarters."""
    quarters = {
        "Q1": "2026-03-31",
        "Q2": "2026-06-30",
        "Q3": "2026-09-30",
        "Q4": "2026-12-31",
    }

    for quarter, expected_date in quarters.items():
        generator = Form13FGenerator(
            cik="0001234567",
            fund_name="Test Fund",
            fiscal_quarter=quarter,
            fiscal_year=2026,
        )
        assert generator.get_period_ended() == expected_date
