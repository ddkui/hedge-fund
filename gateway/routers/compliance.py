# gateway/routers/compliance.py
"""Compliance checking API endpoints."""
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Dict, List
from shared.compliance_checker import ComplianceChecker

router = APIRouter(prefix="/api/compliance", tags=["compliance"])
checker = ComplianceChecker()


class ComplianceCheckRequest(BaseModel):
    """Compliance check request."""
    symbol: str
    quantity: int
    price: float
    action: str  # BUY or SELL
    portfolio_value: float
    current_position_qty: int
    broker_limits: Optional[Dict] = None
    day_trades_today: int = 0
    last_short_price: Optional[float] = None


class ComplianceCheckResponse(BaseModel):
    """Compliance check response."""
    passes: bool
    violations: List[str] = []
    warnings: List[str] = []
    max_allowed_notional: Optional[float] = None
    pdt_day_trades: int = 0


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_trade_compliance(request: ComplianceCheckRequest):
    """Check if trade passes all compliance rules."""
    try:
        result = checker.check_trade(
            symbol=request.symbol,
            quantity=request.quantity,
            price=request.price,
            action=request.action,
            portfolio_value=request.portfolio_value,
            current_position_qty=request.current_position_qty,
            broker_limits=request.broker_limits or {},
            day_trades_today=request.day_trades_today,
            last_short_price=request.last_short_price,
        )

        return ComplianceCheckResponse(
            passes=result.passes,
            violations=result.violations,
            warnings=getattr(result, "warnings", []),
            max_allowed_notional=result.max_allowed_notional,
            pdt_day_trades=result.pdt_day_trades,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/violations")
async def get_violation_history(
    symbol: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
):
    """Get history of compliance violations."""
    try:
        # TODO: Query from database ComplianceViolation table
        return {
            "violations": [],
            "count": 0,
            "symbol_filter": symbol,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
