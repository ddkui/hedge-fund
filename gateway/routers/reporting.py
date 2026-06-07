# gateway/routers/reporting.py
"""Tax and compliance reporting API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime
from shared.tax_calculator import TaxCalculator
from shared.tax_reporter import TaxReporter
from shared.form13f_generator import Form13FGenerator
from shared.audit_exporter import AuditExporter

router = APIRouter(prefix="/api/reporting", tags=["reporting"])


@router.get("/tax-report")
async def get_tax_report(
    year: int = Query(2026),
    tax_lot_method: str = Query("FIFO"),
):
    """Get tax report for year (Schedule D format)."""
    try:
        calc = TaxCalculator(method=tax_lot_method)

        # TODO: Populate from database (Trade table)
        # For now, return stub
        reporter = TaxReporter(calc)
        schedule_d = reporter.generate_schedule_d()

        return {
            "year": year,
            "tax_lot_method": tax_lot_method,
            "short_term_gains": [
                {
                    "symbol": g.symbol,
                    "quantity": g.quantity,
                    "cost_basis": g.cost_basis,
                    "proceeds": g.proceeds,
                    "gain": g.gain,
                    "holding_period": g.holding_period,
                }
                for g in schedule_d["part_i_short_term"]
            ],
            "long_term_gains": [
                {
                    "symbol": g.symbol,
                    "quantity": g.quantity,
                    "cost_basis": g.cost_basis,
                    "proceeds": g.proceeds,
                    "gain": g.gain,
                    "holding_period": g.holding_period,
                }
                for g in schedule_d["part_ii_long_term"]
            ],
            "total_short_term_gain": schedule_d["part_i_total_gain"],
            "total_long_term_gain": schedule_d["part_ii_total_gain"],
            "total_gain": schedule_d["total_gain"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/form-13f")
async def get_form_13f(
    quarter: str = Query("Q1"),
    year: int = Query(2026),
    cik: str = Query("0001234567"),
):
    """Get SEC Form 13F filing for quarter."""
    try:
        generator = Form13FGenerator(
            cik=cik,
            fund_name="Hedge Fund AI",
            fiscal_quarter=quarter,
            fiscal_year=year,
        )

        # TODO: Populate from PortfolioState table
        # For now, return stub
        filing = generator.generate_filing()

        return {
            "cik": filing["cik"],
            "fund_name": filing["fund_name"],
            "period_ended": filing["period_ended"],
            "total_value": filing["total_value"],
            "position_count": filing["position_count"],
            "positions": [
                {
                    "symbol": p.symbol,
                    "quantity": p.quantity,
                    "market_value": p.market_value,
                    "price_per_share": p.price_per_share,
                    "cusip": p.cusip,
                }
                for p in filing["positions"]
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/audit-export")
async def export_audit_log(
    format: str = Query("csv"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """Export audit trail as CSV or PDF."""
    try:
        exporter = AuditExporter()

        # TODO: Populate from Trade table with Signal details
        # For now, return stub CSV
        if format == "pdf":
            pdf_bytes = exporter.export_pdf()
            return {
                "status": "generated",
                "format": "pdf",
                "size_bytes": len(pdf_bytes),
            }
        else:
            csv = exporter.export_csv()
            return {
                "status": "generated",
                "format": "csv",
                "rows": len(csv.split("\n")),
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
