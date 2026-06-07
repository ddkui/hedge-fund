# gateway/routers/analytics.py
"""
API endpoints for analytics: backtesting, correlation hedging, reports.
GET /api/analytics/backtest-results
GET /api/analytics/correlation-hedge
GET /api/analytics/investor-reports
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session

from shared.models import BacktestResult, CorrelationHedgeLog, InvestorReport

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/backtest-results")
async def get_backtest_results(
    db: Session,
    name: str = Query(None),
    limit: int = Query(50, le=500),
):
    """Get historical backtest results."""
    try:
        query = db.query(BacktestResult)
        if name:
            query = query.filter(BacktestResult.name.ilike(f"%{name}%"))
        results = query.order_by(BacktestResult.created_at.desc()).limit(limit).all()
        return {
            "count": len(results),
            "backtests": [
                {
                    "id": r.id,
                    "name": r.name,
                    "start_date": r.start_date.isoformat(),
                    "end_date": r.end_date.isoformat(),
                    "starting_capital": r.starting_capital,
                    "ending_capital": r.ending_capital,
                    "total_return_pct": r.total_return_pct,
                    "total_trades": r.total_trades,
                    "winning_trades": r.winning_trades,
                    "win_rate": r.win_rate,
                    "sharpe_ratio": r.sharpe_ratio,
                    "max_drawdown_pct": r.max_drawdown_pct,
                }
                for r in results
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlation-hedge/status")
async def get_hedge_status(db: Session):
    """Get current correlation hedging status."""
    try:
        latest = (
            db.query(CorrelationHedgeLog)
            .order_by(CorrelationHedgeLog.created_at.desc())
            .first()
        )
        if not latest:
            return {"correlation": None, "hedge_active": False}
        recent = (
            db.query(CorrelationHedgeLog)
            .order_by(CorrelationHedgeLog.created_at.desc())
            .limit(30)
            .all()
        )
        return {
            "correlation": latest.portfolio_correlation,
            "hedge_active": latest.action != "deactivate",
            "hedge_qty": latest.hedge_qty,
            "recent_activity": [
                {
                    "action": r.action,
                    "correlation": r.portfolio_correlation,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/investor-reports")
async def get_investor_reports(
    db: Session,
    investor_id: str = Query(None),
    limit: int = Query(12, le=100),
):
    """Get monthly investor reports."""
    try:
        query = db.query(InvestorReport)
        if investor_id:
            query = query.filter(InvestorReport.investor_id == investor_id)
        reports = query.order_by(InvestorReport.month.desc()).limit(limit).all()
        return {
            "count": len(reports),
            "reports": [
                {
                    "id": r.id,
                    "month": r.month,
                    "monthly_return_pct": r.monthly_return_pct,
                    "sharpe_ratio": r.sharpe_ratio,
                    "total_trades": r.total_trades,
                    "pdf_url": r.pdf_url,
                }
                for r in reports
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
