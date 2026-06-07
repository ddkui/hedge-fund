import pytest
from datetime import datetime
from shared.audit_exporter import AuditExporter, TradeAuditRecord


def test_audit_export_csv_format():
    """Test: Export audit trail as CSV with decision info."""
    exporter = AuditExporter()

    record = TradeAuditRecord(
        trade_id="T001",
        symbol="AAPL",
        action="BUY",
        quantity=100,
        price=150.0,
        executed_at=datetime(2026, 6, 1, 10, 30),
        agent_signals=["technical:bullish:0.85", "sentiment:bullish:0.72"],
        consensus_score=0.78,
        risk_check_passed=True,
        cio_approval_required=False,
        execution_notes="Entry signal aligned across timeframes",
    )

    exporter.add_record(record)
    csv_output = exporter.export_csv()

    assert "trade_id,symbol,action,quantity" in csv_output
    assert "T001,AAPL,BUY,100" in csv_output
    assert "0.78" in csv_output  # Consensus score


def test_audit_export_pdf_with_full_trail():
    """Test: Export PDF with complete decision trail."""
    exporter = AuditExporter()

    record = TradeAuditRecord(
        trade_id="T001",
        symbol="AAPL",
        action="BUY",
        quantity=100,
        price=150.0,
        executed_at=datetime(2026, 6, 1, 10, 30),
        agent_signals=[
            "technical:bullish:0.85",
            "sentiment:bullish:0.72",
            "momentum:neutral:0.50",
        ],
        consensus_score=0.82,
        risk_check_passed=True,
        cio_approval_required=False,
        execution_notes="All signals aligned on entry",
    )

    exporter.add_record(record)
    pdf_bytes = exporter.export_pdf()

    # Basic check: PDF header
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000  # Should be substantial PDF


def test_audit_export_pdf_file_save(tmp_path):
    """Test: Save PDF export to file."""
    exporter = AuditExporter()

    record = TradeAuditRecord(
        trade_id="T001",
        symbol="AAPL",
        action="BUY",
        quantity=100,
        price=150.0,
        executed_at=datetime(2026, 6, 1, 10, 30),
        agent_signals=["technical:bullish:0.85"],
        consensus_score=0.85,
        risk_check_passed=True,
        cio_approval_required=False,
    )

    exporter.add_record(record)

    # Save to temp file
    pdf_path = tmp_path / "audit_trail.pdf"
    with open(pdf_path, "wb") as f:
        f.write(exporter.export_pdf())

    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 1000
