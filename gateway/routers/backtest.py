# gateway/routers/backtest.py
"""
Backtest endpoint: replay historical signals, compare paper vs live execution.
POST /api/backtest/run - Start backtest
GET /api/backtest/results/{test_id} - Get backtest results
GET /api/backtest/compare - Compare paper vs real execution
"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional

from shared.models import BacktestResult, Trade, Signal
from shared.backtester import Backtester, BacktestTrade

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run")
async def run_backtest(
    db: Session,
    start_date: str,  # ISO format: 2026-01-01
    end_date: str,
    name: str = "Default Backtest",
):
    """
    Run a backtest by replaying historical signals against past prices.

    Args:
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
        name: Backtest name for reference

    Returns:
        Backtest ID and status
    """
    try:
        # Parse dates
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        # Query historical signals in date range
        signals = (
            db.query(Signal)
            .filter(
                Signal.created_at >= start,
                Signal.created_at <= end,
            )
            .all()
        )

        if not signals:
            raise HTTPException(
                status_code=400,
                detail=f"No signals found in date range {start_date} to {end_date}",
            )

        # Create backtester
        backtester = Backtester()

        # For each signal, create a trade
        for signal in signals:
            # TODO: Get price at signal time
            signal_price = 100.0  # Placeholder

            # TODO: Get exit price at close of day
            exit_price = 102.0  # Placeholder

            trade = BacktestTrade(
                symbol=signal.symbol,
                date=signal.created_at,
                action="long" if signal.signal_type == "bullish_signal" else "short",
                entry_price=signal_price,
                exit_price=exit_price,
                quantity=1.0,  # Default 1 share
            )
            trade.calculate_pnl()
            backtester.add_trade(trade)

        # Calculate metrics
        metrics = backtester.calculate_metrics()

        # Save results to database
        result = BacktestResult(
            name=name,
            start_date=start,
            end_date=end,
            starting_capital=backtester.starting_capital,
            ending_capital=backtester.starting_capital + metrics.get("total_pnl", 0),
            total_trades=metrics.get("total_trades", 0),
            winning_trades=metrics.get("winning_trades", 0),
            losing_trades=metrics.get("losing_trades", 0),
            win_rate=metrics.get("win_rate", 0),
            total_return_pct=metrics.get("total_returns_pct", 0),
            max_drawdown_pct=0.0,  # TODO: Calculate
            trades_log=backtester.trades,
        )
        db.add(result)
        db.commit()

        return {
            "id": result.id,
            "name": result.name,
            "status": "completed",
            "metrics": metrics,
            "date_range": {
                "start": start_date,
                "end": end_date,
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{test_id}")
async def get_backtest_results(db: Session, test_id: int):
    """Get detailed backtest results."""
    try:
        result = (
            db.query(BacktestResult)
            .filter(BacktestResult.id == test_id)
            .first()
        )

        if not result:
            raise HTTPException(status_code=404, detail="Backtest not found")

        return {
            "id": result.id,
            "name": result.name,
            "start_date": result.start_date.isoformat(),
            "end_date": result.end_date.isoformat(),
            "starting_capital": result.starting_capital,
            "ending_capital": result.ending_capital,
            "total_return_pct": result.total_return_pct,
            "total_trades": result.total_trades,
            "winning_trades": result.winning_trades,
            "losing_trades": result.losing_trades,
            "win_rate": result.win_rate,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown_pct": result.max_drawdown_pct,
            "trades": result.trades_log,
            "created_at": result.created_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare")
async def compare_paper_vs_real(
    db: Session,
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
):
    """
    Compare paper trading (simulated) vs real execution.

    Shows:
    - Paper P&L (from backtest)
    - Real P&L (actual trades)
    - Slippage (difference due to execution quality)
    """
    try:
        # Query paper trades (from BacktestResult)
        paper_query = db.query(BacktestResult)
        if start_date:
            paper_query = paper_query.filter(BacktestResult.start_date >= datetime.fromisoformat(start_date))
        if end_date:
            paper_query = paper_query.filter(BacktestResult.end_date <= datetime.fromisoformat(end_date))

        paper_results = paper_query.all()

        # Query real trades
        real_query = db.query(Trade).filter(Trade.status == "executed")
        if start_date:
            real_query = real_query.filter(Trade.executed_at >= datetime.fromisoformat(start_date))
        if end_date:
            real_query = real_query.filter(Trade.executed_at <= datetime.fromisoformat(end_date))

        real_trades = real_query.all()

        # Calculate totals
        paper_pnl = sum(r.ending_capital - r.starting_capital for r in paper_results)
        real_pnl = sum(t.pnl for t in real_trades if t.pnl)

        slippage = real_pnl - paper_pnl
        slippage_pct = (slippage / paper_pnl * 100) if paper_pnl != 0 else 0

        return {
            "paper_trading": {
                "total_pnl": paper_pnl,
                "num_backtests": len(paper_results),
                "total_trades": sum(r.total_trades for r in paper_results),
            },
            "real_execution": {
                "total_pnl": real_pnl,
                "num_trades": len(real_trades),
                "winning_trades": len([t for t in real_trades if t.pnl and t.pnl > 0]),
            },
            "comparison": {
                "slippage_pnl": slippage,
                "slippage_pct": slippage_pct,
                "efficiency": ((real_pnl / paper_pnl * 100) if paper_pnl > 0 else 0),
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals-replay")
async def replay_signals(
    db: Session,
    agent: Optional[str] = Query(None),
    regime: Optional[str] = Query(None),
    limit: int = Query(50, le=500),
):
    """
    Replay specific signals to see how they would have performed.
    Useful for analyzing agent accuracy by regime.
    """
    try:
        query = db.query(Signal).filter(Signal.created_at.isnot(None))

        if agent:
            query = query.filter(Signal.agent_name == agent)

        if regime:
            query = query.filter(Signal.regime == regime)

        signals = query.order_by(Signal.created_at.desc()).limit(limit).all()

        replay_results = []
        for signal in signals:
            # Get outcome if exists
            outcome = None
            if signal.outcomes:
                outcome_data = signal.outcomes[0]
                outcome = {
                    "won": outcome_data.won,
                    "pnl": outcome_data.pnl,
                    "pnl_pct": outcome_data.pnl_pct,
                    "closed_at": outcome_data.closed_at.isoformat() if outcome_data.closed_at else None,
                }

            replay_results.append({
                "id": signal.id,
                "agent": signal.agent_name,
                "symbol": signal.symbol,
                "signal_type": signal.signal_type,
                "confidence": signal.confidence,
                "regime": signal.regime,
                "created_at": signal.created_at.isoformat(),
                "outcome": outcome,
            })

        return {
            "count": len(replay_results),
            "signals": replay_results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
