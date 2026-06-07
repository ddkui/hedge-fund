# shared/trade_audit.py
"""
Trade audit trail - records all trades with consensus scores and rejection reasons.
Enables transparency and optimization.
"""
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional


@dataclass
class TradeAuditRecord:
    trade_id: int
    symbol: str
    action: str  # "long" or "short"
    quantity: float
    consensus_score: float
    confidence: float
    regime: str
    agent_signals: dict  # per-agent scores
    status: str  # "executed", "rejected", "pending"
    rejection_reason: Optional[str] = None
    risk_check_reason: Optional[str] = None
    cio_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    final_price: Optional[float] = None
    pnl: Optional[float] = None

    def to_dict(self) -> dict:
        """Convert to dict for storage."""
        data = asdict(self)
        # Serialize datetimes to ISO format
        if data.get("created_at"):
            data["created_at"] = data["created_at"].isoformat()
        if data.get("executed_at"):
            data["executed_at"] = data["executed_at"].isoformat()
        return data


class TradeAuditLog:
    def __init__(self):
        self.records: list[TradeAuditRecord] = []

    def add_record(self, record: TradeAuditRecord) -> None:
        """Log a trade decision."""
        if record.created_at is None:
            record.created_at = datetime.now(timezone.utc)
        self.records.append(record)

    def get_by_symbol(self, symbol: str) -> list[TradeAuditRecord]:
        """Get all audits for a symbol."""
        return [r for r in self.records if r.symbol == symbol]

    def get_by_status(self, status: str) -> list[TradeAuditRecord]:
        """Get all audits with given status."""
        return [r for r in self.records if r.status == status]

    def get_rejected(self) -> list[TradeAuditRecord]:
        """Get all rejected trades with reasons."""
        return [
            r for r in self.records
            if r.status == "rejected"
        ]

    def get_all(self) -> list[dict]:
        """Export all records as dicts."""
        return [r.to_dict() for r in self.records]
