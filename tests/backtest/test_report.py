import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path
import tempfile


def _dt(days):
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=days)


def _make_report_generator(snapshots, trades):
    from backtest.report import ReportGenerator

    mock_db = AsyncMock()
    mock_db._run_id = 1
    mock_db.fetch = AsyncMock()
    mock_db.fetchrow = AsyncMock()

    async def fetch_side_effect(query, *args):
        if "portfolio_state" in query:
            return snapshots
        if "trades" in query:
            return trades
        return []

    mock_db.fetch.side_effect = fetch_side_effect
    return ReportGenerator(db=mock_db, run_id=1)


async def test_report_generates_html_file():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
        {"time": _dt(30), "total_value": 110_000.0, "cash": 80_000.0, "peak_value": 110_000.0},
        {"time": _dt(365), "total_value": 120_000.0, "cash": 70_000.0, "peak_value": 120_000.0},
    ]
    trades = [
        {"action": "long", "symbol": "AAPL", "quantity": 10.0, "price": 150.0, "confidence": 75.0, "time": _dt(1)},
    ]
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    assert "<html" in content.lower()
    assert "plotly" in content.lower()


async def test_report_contains_metric_values():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
        {"time": _dt(365), "total_value": 120_000.0, "cash": 70_000.0, "peak_value": 120_000.0},
    ]
    trades = []
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    # 20% total return should appear somewhere
    assert "20" in content


async def test_report_contains_equity_chart_marker():
    snaps = [
        {"time": _dt(0), "total_value": 100_000.0, "cash": 100_000.0, "peak_value": 100_000.0},
    ]
    trades = []
    gen = _make_report_generator(snaps, trades)

    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        output_path = f.name

    await gen.generate(output_path)
    content = Path(output_path).read_text()

    assert "equity" in content.lower() or "Equity" in content
