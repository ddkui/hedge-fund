# tests/conftest.py
"""
Comprehensive pytest fixtures and factories for extensible testing.
All tests can build on these without brittle dependencies.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone


# ============================================================================
# DATABASE FIXTURES (reusable across any test)
# ============================================================================

@pytest.fixture
def mock_db():
    """Generic mock database connection."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.fetchval = AsyncMock(return_value=None)
    return db


@pytest.fixture
def mock_bus():
    """Generic mock Redis bus."""
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)
    bus.set = AsyncMock()
    bus.delete = AsyncMock()
    bus.publish = AsyncMock()
    return bus


# ============================================================================
# DATA BUILDERS (factories to construct realistic test data)
# ============================================================================

class TradeBuilder:
    """Build realistic trade objects for testing."""
    def __init__(self):
        self.data = {
            "id": 1,
            "symbol": "AAPL",
            "action": "long",
            "quantity": 10.0,
            "paper": True,
            "broker": None,
            "asset_class": "stock",
            "status": "pending",
            "created_at": datetime.now(timezone.utc),
        }

    def with_symbol(self, symbol: str) -> "TradeBuilder":
        self.data["symbol"] = symbol
        return self

    def with_quantity(self, qty: float) -> "TradeBuilder":
        self.data["quantity"] = qty
        return self

    def with_action(self, action: str) -> "TradeBuilder":
        self.data["action"] = action
        return self

    def with_status(self, status: str) -> "TradeBuilder":
        self.data["status"] = status
        return self

    def as_live(self) -> "TradeBuilder":
        self.data["paper"] = False
        return self

    def for_broker(self, broker: str) -> "TradeBuilder":
        self.data["broker"] = broker
        return self

    def build(self) -> dict:
        return self.data.copy()


class SignalBuilder:
    """Build realistic signal objects for testing."""
    def __init__(self):
        self.data = {
            "agent": "technical",
            "symbol": "AAPL",
            "signal_type": "bullish_signal",
            "confidence": 75.0,
            "regime": "expansion",
            "reasoning": "Test signal",
            "metadata": {},
        }

    def from_agent(self, agent: str) -> "SignalBuilder":
        self.data["agent"] = agent
        return self

    def with_symbol(self, symbol: str) -> "SignalBuilder":
        self.data["symbol"] = symbol
        return self

    def bearish(self) -> "SignalBuilder":
        self.data["signal_type"] = "bearish_signal"
        return self

    def with_confidence(self, conf: float) -> "SignalBuilder":
        self.data["confidence"] = conf
        return self

    def in_regime(self, regime: str) -> "SignalBuilder":
        self.data["regime"] = regime
        return self

    def build(self) -> dict:
        return self.data.copy()


class PortfolioStateBuilder:
    """Build realistic portfolio state for testing."""
    def __init__(self):
        self.data = {
            "cash": 100000.0,
            "total_value": 100000.0,
            "peak_value": 100000.0,
            "open_positions": 0,
            "time": datetime.now(timezone.utc),
        }

    def with_cash(self, cash: float) -> "PortfolioStateBuilder":
        self.data["cash"] = cash
        return self

    def with_total_value(self, value: float) -> "PortfolioStateBuilder":
        self.data["total_value"] = value
        return self

    def with_open_positions(self, count: int) -> "PortfolioStateBuilder":
        self.data["open_positions"] = count
        return self

    def in_drawdown(self, pct: float) -> "PortfolioStateBuilder":
        peak = self.data["peak_value"]
        self.data["total_value"] = peak * (1 - pct / 100)
        return self

    def build(self) -> dict:
        return self.data.copy()


@pytest.fixture
def trade_builder():
    """Fixture for building trades."""
    return TradeBuilder()


@pytest.fixture
def signal_builder():
    """Fixture for building signals."""
    return SignalBuilder()


@pytest.fixture
def portfolio_builder():
    """Fixture for building portfolio state."""
    return PortfolioStateBuilder()


# ============================================================================
# MOCK RESPONSE BUILDERS (for common API responses)
# ============================================================================

@pytest.fixture
def broker_fill_response():
    """Mock broker fill response."""
    return {
        "broker_name": "alpaca",
        "status": "filled",
        "fill_price": 185.50,
        "fill_qty": 10.0,
        "error_msg": None,
    }


@pytest.fixture
def risk_check_pass():
    """Mock risk agent approval."""
    return {"approved": True, "reason": "Within limits"}


@pytest.fixture
def risk_check_fail():
    """Mock risk agent rejection."""
    return {"approved": False, "reason": "Drawdown > 20%"}


# ============================================================================
# ASSERTION HELPERS (reduce test brittleness)
# ============================================================================

class AssertHelper:
    """Helper methods for clean assertions."""

    @staticmethod
    def assert_trade_executed(mock_db, symbol: str, qty: float = None):
        """Assert a trade was executed without brittle full-state checks."""
        calls = mock_db.execute.call_args_list
        trade_updates = [
            c for c in calls
            if "UPDATE trades" in str(c) and symbol in str(c)
        ]
        assert len(trade_updates) > 0, f"No trade execution found for {symbol}"

    @staticmethod
    def assert_portfolio_updated(mock_db):
        """Assert portfolio state was updated."""
        calls = mock_db.execute.call_args_list
        portfolio_calls = [
            c for c in calls
            if "INSERT INTO portfolio_state" in str(c)
        ]
        assert len(portfolio_calls) > 0, "Portfolio state not updated"

    @staticmethod
    def assert_signal_published(mock_bus, agent: str = None):
        """Assert a signal was published."""
        calls = mock_bus.publish.call_args_list
        if agent:
            agent_calls = [c for c in calls if agent in str(c)]
            assert len(agent_calls) > 0, f"No signal published by {agent}"
        else:
            assert len(calls) > 0, "No signals published"


@pytest.fixture
def assert_helper():
    """Fixture for assertion helpers."""
    return AssertHelper()


# ============================================================================
# COMMON MOCKS
# ============================================================================

@pytest.fixture
def mock_settings():
    """Mock application settings."""
    settings = MagicMock()
    settings.initial_capital = 100000.0
    settings.paper_trading = True
    settings.max_loss_pct = 5.0
    settings.allowed_login_emails = "test@example.com"
    settings.jwt_secret = "test-secret"
    return settings


@pytest.fixture
def mock_logger():
    """Mock logger."""
    return MagicMock()
