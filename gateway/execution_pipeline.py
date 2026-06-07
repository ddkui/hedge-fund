# gateway/execution_pipeline.py
"""
Integrated execution pipeline wiring all 10 improvements.
Orchestrates: signal → audit → risk check → execution → fills → reporting
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from shared.circuit_breaker import CircuitBreaker
from shared.broker_failover import BrokerFailover
from shared.position_sizer import PositionSizer
from shared.regime_monitor import RegimeMonitor
from shared.trade_audit import TradeAuditLog, TradeAuditRecord
from shared.volatility_executor import VolatilityExecutor
from shared.agent_memory import AgentMemory
from shared.correlation_hedger import CorrelationHedger
from shared.models import Trade, BrokerFill, TradeStatus, RiskEvent


class ExecutionPipeline:
    """
    Integrated pipeline: signal → audit → risk → execution → fills → reporting
    """

    def __init__(
        self,
        db: Session,
        circuit_breaker: CircuitBreaker,
        broker_failover: BrokerFailover,
        position_sizer: PositionSizer,
        regime_monitor: RegimeMonitor,
        audit_log: TradeAuditLog,
        volatility_executor: VolatilityExecutor,
        agent_memory: AgentMemory,
        correlation_hedger: CorrelationHedger,
    ):
        self.db = db
        self.cb = circuit_breaker
        self.failover = broker_failover
        self.sizer = position_sizer
        self.regime = regime_monitor
        self.audit = audit_log
        self.executor = volatility_executor
        self.memory = agent_memory
        self.hedger = correlation_hedger

    async def execute_signal(
        self,
        signal: dict,
        portfolio_value: float,
        peak_value: float,
        current_vix: float,
        broker_equity_map: dict,
    ) -> Optional[Trade]:
        """
        Execute a signal through complete pipeline.

        Flow:
        1. Check circuit breaker (safety)
        2. Log to audit trail
        3. Check risk limits
        4. Size position by equity
        5. Check correlation hedge
        6. Execute with volatility awareness
        7. Handle failover if needed
        8. Record fills
        9. Update portfolio
        10. Log outcome for agent memory

        Returns:
            Executed trade or None if rejected
        """

        # ========== STEP 1: CIRCUIT BREAKER ==========
        is_tripped, cb_reason = self.cb.check(portfolio_value, peak_value)
        if is_tripped:
            await self._log_risk_event(
                "circuit_breaker",
                "critical",
                cb_reason,
                {"portfolio_value": portfolio_value, "peak_value": peak_value},
            )
            return None

        # ========== STEP 2: AUDIT TRAIL ==========
        # Apply agent memory confidence adjustment
        adjusted_confidence = signal.get("confidence", 75.0)
        multiplier = self.memory.get_confidence_multiplier(
            signal.get("agent", "unknown"),
            self.regime.get_regime().value,
        )
        adjusted_confidence *= multiplier

        # Create audit record
        audit_record = TradeAuditRecord(
            trade_id=None,  # Will be set after DB insert
            symbol=signal["symbol"],
            action=signal["action"],
            quantity=signal.get("quantity", 0),
            consensus_score=signal.get("consensus_score", 0),
            confidence=adjusted_confidence,
            regime=self.regime.get_regime().value,
            agent_signals=signal.get("agent_signals", {}),
            status="pending",
        )
        self.audit.add_record(audit_record)

        # ========== STEP 3: RISK CHECK ==========
        risk_approved = await self._check_risk(signal, portfolio_value)
        if not risk_approved:
            audit_record.status = "rejected"
            audit_record.rejection_reason = "Risk check failed"
            self.audit.add_record(audit_record)
            return None

        # ========== STEP 4: POSITION SIZING ==========
        sized_trades = []
        for broker_name, equity in broker_equity_map.items():
            adjusted_qty = self.sizer.calculate_qty(
                signal_qty=signal.get("quantity", 100),
                account_equity=equity,
                price=signal.get("price", 100),
            )
            sized_trades.append(
                {
                    "broker": broker_name,
                    "symbol": signal["symbol"],
                    "action": signal["action"],
                    "qty": adjusted_qty,
                    "price": signal.get("price", 100),
                }
            )

        # ========== STEP 5: CORRELATION HEDGE ==========
        hedge_order = None
        if self.hedger.should_hedge():
            hedge_qty = self.hedger.calculate_hedge_qty(
                portfolio_value, signal.get("spy_price", 400)
            )
            if not self.hedger.is_hedged():
                hedge_order = self.hedger.apply_hedge(hedge_qty)
                await self._log_risk_event(
                    "hedge_activation",
                    "warning",
                    f"Portfolio correlation {self.hedger.current_correlation:.2f} > {self.hedger.correlation_threshold}",
                    {"hedge_qty": hedge_qty},
                )

        # ========== STEP 6-7: EXECUTE WITH FAILOVER ==========
        all_fills = []
        for sized_trade in sized_trades:
            # Get order type based on volatility
            order_type = self.executor.get_order_type(current_vix, sized_trade["qty"])
            sized_trade["order_type"] = order_type

            if order_type == "limit":
                limit_price = self.executor.calculate_limit_price(
                    sized_trade["price"],
                    sized_trade["action"],
                    current_vix,
                )
                sized_trade["limit_price"] = limit_price

            # TODO: Actually execute with broker (placeholder)
            fill = await self._execute_with_broker(sized_trade)
            all_fills.append(fill)

        # Failover for any failed fills
        fills = await self.failover.execute_with_failover(sized_trade, all_fills)

        # Mark dead brokers
        for fill in fills:
            if fill.status == "error":
                await self.failover.mark_broker_dead(fill.broker_name)
            elif fill.status == "filled":
                await self.failover.mark_broker_healthy(fill.broker_name)

        # ========== STEP 8: RECORD FILLS ==========
        trade = Trade(
            symbol=signal["symbol"],
            action=signal["action"],
            quantity=sum(f.fill_qty for f in fills if f.fill_qty),
            entry_price=signal.get("price", 0),
            consensus_score=signal.get("consensus_score", 0),
            confidence=adjusted_confidence,
            regime=self.regime.get_regime().value,
            agent_signals=signal.get("agent_signals", {}),
            status=TradeStatus.EXECUTED,
            executed_at=datetime.now(timezone.utc),
        )

        for fill in fills:
            broker_fill = BrokerFill(
                broker_name=fill.broker_name,
                status=fill.status,
                fill_price=fill.fill_price,
                fill_qty=fill.fill_qty,
                error_msg=fill.error_msg,
            )
            trade.broker_fills.append(broker_fill)

        self.db.add(trade)
        self.db.commit()

        # Update audit record with trade ID
        audit_record.trade_id = trade.id
        audit_record.status = "executed"
        audit_record.executed_at = datetime.now(timezone.utc)
        audit_record.final_price = sum(
            f.fill_price * f.fill_qty for f in fills if f.fill_price
        ) / sum(f.fill_qty for f in fills if f.fill_qty)
        self.audit.add_record(audit_record)

        # ========== STEP 9: UPDATE PORTFOLIO ==========
        # TODO: Calculate P&L and update portfolio state
        # (This will be done by separate portfolio updater job)

        # ========== STEP 10: LOG OUTCOME FOR AGENT MEMORY ==========
        # Outcome will be recorded later when trade closes
        # For now, just note that trade was executed

        return trade

    async def _check_risk(self, signal: dict, portfolio_value: float) -> bool:
        """
        Check if trade passes risk agent review.
        Currently returns True; in production, call actual risk agent.
        """
        # TODO: Call actual risk agent microservice
        # risk_result = await risk_agent_service.check(signal, portfolio_value)
        # return risk_result["approved"]
        return True

    async def _execute_with_broker(self, trade: dict):
        """
        Execute trade with broker.
        Placeholder - TODO: integrate actual broker APIs.
        """
        from shared.brokers.base import BrokerFill

        # TODO: Call actual broker.fill(trade) with asyncio.gather
        return BrokerFill(
            broker_name=trade["broker"],
            status="filled",
            fill_price=trade["price"],
            fill_qty=trade["qty"],
            error_msg=None,
        )

    async def _log_risk_event(
        self,
        event_type: str,
        severity: str,
        message: str,
        metadata: dict = None,
    ):
        """Log a risk event to database."""
        event = RiskEvent(
            event_type=event_type,
            severity=severity,
            message=message,
            metadata=metadata or {},
        )
        self.db.add(event)
        self.db.commit()
