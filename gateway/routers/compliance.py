# gateway/routers/compliance.py
"""
REST API endpoints for compliance checking.
Provides pre-trade validation against SEC rules, PDT, and risk limits.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
from shared.compliance_checker import ComplianceChecker

router = APIRouter(prefix="/api/compliance", tags=["compliance"])
checker = ComplianceChecker()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class CheckTradeRequest(BaseModel):
    """Request to check trade compliance."""
    symbol: str = Field(..., min_length=1, max_length=5, description="Stock symbol (e.g., AAPL)")
    action: str = Field(..., description="Trade direction: 'long' or 'short'")
    quantity: float = Field(..., gt=0, description="Number of shares")
    position_limit_pct: float = Field(0.05, ge=0.001, le=0.50, description="Max position as % of portfolio")
    day_trades_today: int = Field(0, ge=0, description="Count of day trades executed today")
    last_short_price: Optional[float] = Field(None, description="Price of last short (for uptick rule)")
    broker_limits: Optional[Dict] = Field(None, description="Broker-specific limits (reserved)")


class CheckShortSaleRequest(BaseModel):
    """Request to check short sale compliance."""
    symbol: str = Field(..., min_length=1, max_length=5, description="Stock symbol")
    quantity: float = Field(..., gt=0, description="Number of shares to short")
    current_price: float = Field(..., gt=0, description="Current market price")
    last_short_price: Optional[float] = Field(None, description="Price of last short")


class CheckPDTStatusRequest(BaseModel):
    """Request to check PDT account status."""
    account_type: str = Field(..., description="'margin' or 'cash'")
    equity: float = Field(..., gt=0, description="Account equity in dollars")
    day_trades_count: int = Field(..., ge=0, description="Day trades in last 5 trading days")


class ComplianceCheckResponse(BaseModel):
    """Response with compliance check result."""
    passes: bool = Field(..., description="True if all checks pass")
    violations: List[str] = Field(default_factory=list, description="List of violations found")
    warnings: List[str] = Field(default_factory=list, description="List of warnings")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post("/check-trade", response_model=ComplianceCheckResponse)
async def check_trade(request: CheckTradeRequest) -> ComplianceCheckResponse:
    """
    Check if a trade passes compliance checks.

    Validates against:
    - Quantity limits (0 < qty <= 10,000)
    - Symbol format (1-5 uppercase chars)
    - Action type (long/short)
    - Pattern Day Trading rule (max 3 day trades)
    - Position size limits
    - Short sale requirements

    Returns passes=True if all validations pass, violations list if any fail.
    """
    try:
        result = checker.check_trade(
            symbol=request.symbol,
            action=request.action,
            quantity=request.quantity,
            position_limit_pct=request.position_limit_pct,
            day_trades_today=request.day_trades_today,
            last_short_price=request.last_short_price,
            broker_limits=request.broker_limits or {},
        )

        return ComplianceCheckResponse(
            passes=result.passes,
            violations=result.violations,
            warnings=result.warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-short-sale", response_model=ComplianceCheckResponse)
async def check_short_sale(request: CheckShortSaleRequest) -> ComplianceCheckResponse:
    """
    Check if a short sale passes compliance checks.

    Validates against:
    - Uptick rule (short price >= last short price)
    - Quantity limits
    - Symbol format

    Returns passes=True if short is allowed.
    """
    try:
        result = checker.check_short_sale(
            symbol=request.symbol,
            quantity=request.quantity,
            current_price=request.current_price,
            last_short_price=request.last_short_price,
        )

        return ComplianceCheckResponse(
            passes=result.passes,
            violations=result.violations,
            warnings=result.warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/check-pdt-status", response_model=ComplianceCheckResponse)
async def check_pdt_status(request: CheckPDTStatusRequest) -> ComplianceCheckResponse:
    """
    Check Pattern Day Trader (PDT) account status.

    Validates:
    - Margin account with 4+ day trades requires $25k+ equity
    - Cash accounts have no PDT restrictions
    - Account type validity

    Returns passes=True if PDT rules are satisfied.
    """
    try:
        result = checker.check_pdt_status(
            account_type=request.account_type,
            equity=request.equity,
            day_trades_count=request.day_trades_count,
        )

        return ComplianceCheckResponse(
            passes=result.passes,
            violations=result.violations,
            warnings=result.warnings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_compliance_rules() -> dict:
    """
    Get a summary of compliance rules enforced.

    Returns:
        Dictionary with rule descriptions and limits.
    """
    return {
        "rules": {
            "quantity": {
                "description": "Trade quantity constraints",
                "min": 0,
                "max": 10000,
            },
            "symbol": {
                "description": "Symbol format",
                "min_length": 1,
                "max_length": 5,
                "must_be_uppercase": True,
            },
            "pdt": {
                "description": "Pattern Day Trading rule",
                "max_day_trades_per_day": 3,
                "margin_min_equity": 25000,
                "applies_to": "margin_accounts",
            },
            "position_limit": {
                "description": "Maximum position size",
                "typical_range": "1-50% of portfolio",
            },
            "short_sale": {
                "description": "Short selling rules",
                "uptick_rule": "Short price >= last short price (within 1% tolerance)",
            },
        },
    }
