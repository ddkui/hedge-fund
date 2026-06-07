# gateway/routers/audit.py
"""
API endpoints for trade audit trail (SEC compliance).
GET /api/audit/trades - Export audit log
"""
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import List

from shared.models import Trade, TradeStatus

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/trades")
async def get_audit_trail(
    db: Session,
    symbol: str = Query(None),
    status: str = Query(None),
    start_date: datetime = Query(None),
    end_date: datetime = Query(None),
    limit: int = Query(100, le=1000),
):
    """
    Get audit trail of all trades with decision metadata.

    Query params:
    - symbol: Filter by symbol (e.g., "AAPL")
    - status: Filter by status (pending, executed, rejected, failed)
    - start_date: ISO format datetime
    - end_date: ISO format datetime
    - limit: Max results (default 100, max 1000)

    Response includes:
    - Trade ID, symbol, action, quantity
    - Consensus score, confidence, regime
    - Per-agent signal scores
    - Execution status and price
    - P&L
    """
    try:
        query = db.query(Trade)

        if symbol:
            query = query.filter(Trade.symbol == symbol)

        if status:
            try:
                status_enum = TradeStatus[status.upper()]
                query = query.filter(Trade.status == status_enum)
            except KeyError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid status. Choose from: {[s.value for s in TradeStatus]}",
                )

        if start_date:
            query = query.filter(Trade.created_at >= start_date)

        if end_date:
            query = query.filter(Trade.created_at <= end_date)

        trades = query.order_by(Trade.created_at.desc()).limit(limit).all()

        return {
            "count": len(trades),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "action": t.action,
                    "quantity": t.quantity,
                    "consensus_score": t.consensus_score,
                    "confidence": t.confidence,
                    "regime": t.regime,
                    "agent_signals": t.agent_signals,
                    "status": t.status.value,
                    "rejection_reason": t.rejection_reason,
                    "entry_price": t.entry_price,
                    "exit_price": t.exit_price,
                    "pnl": t.pnl,
                    "pnl_pct": t.pnl_pct,
                    "created_at": t.created_at.isoformat(),
                    "executed_at": t.executed_at.isoformat() if t.executed_at else None,
                    "broker_fills": [
                        {
                            "broker": bf.broker_name,
                            "status": bf.status,
                            "fill_price": bf.fill_price,
                            "fill_qty": bf.fill_qty,
                            "commission": bf.commission,
                            "error_msg": bf.error_msg,
                        }
                        for bf in t.broker_fills
                    ],
                }
                for t in trades
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trades/{trade_id}")
async def get_trade_detail(db: Session, trade_id: int):
    """Get detailed audit record for single trade."""
    try:
        trade = db.query(Trade).filter(Trade.id == trade_id).first()

        if not trade:
            raise HTTPException(status_code=404, detail="Trade not found")

        return {
            "id": trade.id,
            "symbol": trade.symbol,
            "action": trade.action,
            "quantity": trade.quantity,
            "consensus_score": trade.consensus_score,
            "confidence": trade.confidence,
            "regime": trade.regime,
            "agent_signals": trade.agent_signals,
            "status": trade.status.value,
            "rejection_reason": trade.rejection_reason,
            "risk_check_reason": trade.risk_check_reason,
            "entry_price": trade.entry_price,
            "exit_price": trade.exit_price,
            "pnl": trade.pnl,
            "pnl_pct": trade.pnl_pct,
            "created_at": trade.created_at.isoformat(),
            "executed_at": trade.executed_at.isoformat() if trade.executed_at else None,
            "broker_fills": [
                {
                    "id": bf.id,
                    "broker": bf.broker_name,
                    "status": bf.status,
                    "fill_price": bf.fill_price,
                    "fill_qty": bf.fill_qty,
                    "commission": bf.commission,
                    "error_msg": bf.error_msg,
                    "created_at": bf.created_at.isoformat(),
                }
                for bf in trade.broker_fills
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rejected-trades")
async def get_rejected_trades(
    db: Session,
    limit: int = Query(50, le=500),
):
    """
    Get all rejected trades with rejection reasons.
    Useful for analysis: why are trades being rejected?
    """
    try:
        rejected = (
            db.query(Trade)
            .filter(Trade.status == TradeStatus.REJECTED)
            .order_by(Trade.created_at.desc())
            .limit(limit)
            .all()
        )

        return {
            "count": len(rejected),
            "trades": [
                {
                    "id": t.id,
                    "symbol": t.symbol,
                    "action": t.action,
                    "consensus_score": t.consensus_score,
                    "confidence": t.confidence,
                    "rejection_reason": t.rejection_reason,
                    "risk_check_reason": t.risk_check_reason,
                    "created_at": t.created_at.isoformat(),
                }
                for t in rejected
            ],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_audit_stats(db: Session):
    """
    Get trading statistics from audit trail.
    Total trades, execution rate, rejection rate, etc.
    """
    try:
        total = db.query(Trade).count()
        executed = db.query(Trade).filter(Trade.status == TradeStatus.EXECUTED).count()
        rejected = db.query(Trade).filter(Trade.status == TradeStatus.REJECTED).count()
        failed = db.query(Trade).filter(Trade.status == TradeStatus.FAILED).count()

        successful_trades = (
            db.query(Trade)
            .filter(
                Trade.status == TradeStatus.EXECUTED,
                Trade.pnl.isnot(None),
            )
            .all()
        )

        total_pnl = sum(t.pnl for t in successful_trades if t.pnl)
        winning = len([t for t in successful_trades if t.pnl and t.pnl > 0])

        return {
            "total_trades": total,
            "executed": executed,
            "rejected": rejected,
            "failed": failed,
            "execution_rate": (executed / total * 100) if total > 0 else 0,
            "win_rate": (winning / len(successful_trades) * 100)
            if successful_trades
            else 0,
            "total_pnl": total_pnl,
            "avg_pnl": (total_pnl / len(successful_trades))
            if successful_trades
            else 0,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
