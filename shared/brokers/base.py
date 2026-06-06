# shared/brokers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class BrokerFill:
    broker_name: str
    trade_id: int
    status: str               # "filled" | "rejected" | "error"
    fill_price: float | None
    fill_qty: float | None
    error_msg: str | None
    time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BrokerAdapter(ABC):
    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    async def fill(self, trade: dict) -> BrokerFill: ...

    @abstractmethod
    async def is_available(self) -> bool: ...
