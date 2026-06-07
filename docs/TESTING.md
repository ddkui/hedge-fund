# Testing Guide: Extensible Test Suite

This guide explains how to add new tests without breaking existing code. The test suite is designed for **regression prevention** and **easy extension**.

---

## Core Principles

### 1. TDD First
Write the test **before** the implementation:
```python
def test_my_feature():
    result = my_new_function(input_data)
    assert result == expected_value
```

### 2. Data Builders (Not Fixtures)
Use builders for complex test data—they're composable and clear:

```python
def test_resize_order_by_equity(trade_builder):
    trade = trade_builder.with_symbol("AAPL").with_quantity(100).as_live().build()
    # vs
    trade = {
        "symbol": "AAPL",
        "quantity": 100,
        "paper": False,
        "broker": None,
        "asset_class": "stock",
        ...
    }
```

### 3. Assertion Helpers
Use helpers instead of brittle state checks:

```python
# ✅ Good: flexible
assert_helper.assert_trade_executed(mock_db, "AAPL")

# ❌ Bad: breaks if internal structure changes
assert mock_db.execute.call_args_list[0][0][0] == "UPDATE trades ..."
```

### 4. Mock External Dependencies
Stub out APIs, databases, brokers:

```python
mock_broker = AsyncMock()
mock_broker.fill = AsyncMock(return_value=BrokerFill(...))
```

Internal logic is fully tested; external systems are mocked to prevent flakiness.

---

## Test Organization

```
tests/
├── conftest.py                 # Shared fixtures, builders, helpers
├── shared/
│   ├── test_circuit_breaker.py
│   ├── test_broker_failover.py
│   ├── test_position_sizer.py
│   ├── test_regime_monitor.py
│   ├── test_trade_audit.py
│   ├── test_volatility_executor.py
│   ├── test_agent_memory.py
│   ├── test_backtester.py
│   ├── test_correlation_hedger.py
│   ├── test_investor_report.py
│   └── test_improvements.py    # All 10 improvements in one place
├── gateway/
│   ├── test_auth_google.py
│   ├── test_brokers_router.py
│   └── ...
└── integration/
    ├── test_execution_flow.py  # End-to-end: signal → execution
    └── test_portfolio_updates.py
```

---

## Adding New Tests

### Pattern 1: Feature Test (Happy Path)
```python
class TestMyNewFeature:
    def test_basic_functionality(self):
        """Test the main use case."""
        obj = MyClass()
        result = obj.do_something(input_data)
        assert result == expected_output
```

### Pattern 2: Error Handling
```python
def test_handles_invalid_input(self):
    """Test error handling."""
    obj = MyClass()
    with pytest.raises(ValueError, match="Invalid"):
        obj.do_something(bad_input)
```

### Pattern 3: State Changes
```python
def test_state_transition(self, mock_db):
    """Test database updates without checking exact SQL."""
    obj = MyClass(db=mock_db)
    obj.process()
    
    # Use helper instead of checking exact call
    assert_helper.assert_portfolio_updated(mock_db)
```

### Pattern 4: Async Operations
```python
@pytest.mark.asyncio
async def test_async_operation(self):
    """Test async functions."""
    result = await my_async_function(data)
    assert result is not None
```

### Pattern 5: Using Builders
```python
def test_with_multiple_scenarios(self, trade_builder):
    """Reuse builder for multiple test cases."""
    # Small order
    small = trade_builder.with_quantity(10).build()
    assert sizer.calculate_qty(small) <= 10
    
    # Large order
    large = trade_builder.with_quantity(1000).build()
    assert sizer.calculate_qty(large) <= expected_max
```

---

## Fixture & Builder Reference

### Pre-Built Fixtures (in conftest.py)

```python
# Database and messaging
mock_db              # AsyncMock database
mock_bus             # AsyncMock Redis

# Data builders
trade_builder        # Build realistic trades
signal_builder       # Build realistic signals
portfolio_builder    # Build portfolio state

# Mock responses
broker_fill_response # Sample broker fill
risk_check_pass      # Risk agent approval
risk_check_fail      # Risk agent rejection

# Helpers
assert_helper        # Assertion utilities
mock_settings        # App settings
mock_logger          # Logger mock
```

### TradeBuilder Example
```python
trade = (trade_builder
    .with_symbol("AAPL")
    .with_quantity(100)
    .with_action("short")
    .with_status("pending")
    .as_live()
    .for_broker("alpaca")
    .build())
```

### SignalBuilder Example
```python
signal = (signal_builder
    .from_agent("technical")
    .with_symbol("MSFT")
    .bearish()
    .with_confidence(85.0)
    .in_regime("crisis")
    .build())
```

---

## Running Tests

### Run All Tests
```bash
pytest tests/ -v
```

### Run Specific Module
```bash
pytest tests/shared/test_circuit_breaker.py -v
```

### Run Specific Test
```bash
pytest tests/shared/test_circuit_breaker.py::TestCircuitBreaker::test_circuit_trips_at_loss_limit -v
```

### Run with Coverage
```bash
pytest tests/ --cov=shared --cov=gateway --cov-report=html
```

### Run Only Fast Tests (no async/DB)
```bash
pytest tests/ -m "not integration"
```

---

## Test Patterns to Follow

### ✅ Good Test Patterns

**1. Clear Test Names (What → Expected)**
```python
def test_circuit_breaks_when_loss_exceeds_limit():  # Good
def test_circuit():  # Bad
```

**2. One Assertion Per Test (When Possible)**
```python
def test_limit_order_for_high_vix():
    executor = VolatilityExecutor()
    order_type = executor.get_order_type(vix=35, qty=100)
    assert order_type == "limit"  # One thing tested
```

**3. Setup-Execute-Assert Pattern**
```python
def test_position_scales_with_equity():
    # Setup
    sizer = PositionSizer()
    
    # Execute
    small_qty = sizer.scale_qty_by_equity(100, 100000, 100000)
    large_qty = sizer.scale_qty_by_equity(100, 100000, 500000)
    
    # Assert
    assert large_qty == 5 * small_qty
```

**4. Use Builders for Readability**
```python
trade = trade_builder.with_symbol("AAPL").with_quantity(100).build()
# vs
trade = {"symbol": "AAPL", "quantity": 100, ...}
```

### ❌ Patterns to Avoid

**1. Testing Implementation Details**
```python
# Bad: breaks if we refactor _internal_method
assert obj._internal_method.call_count == 1

# Good: test the actual behavior
assert result == expected_output
```

**2. Brittle String Matching**
```python
# Bad: breaks if SQL formatting changes
assert "UPDATE trades SET status = 'executed'" in str(call)

# Good: use helper
assert_helper.assert_trade_executed(mock_db, "AAPL")
```

**3. Large Monolithic Tests**
```python
# Bad: multiple things tested, hard to debug
def test_entire_trading_flow():
    obj = MyClass()
    obj.do_a()
    obj.do_b()
    obj.do_c()
    assert many_things

# Good: one test per behavior
def test_enables_trading():
    obj = MyClass()
    obj.enable()
    assert obj.is_enabled()
```

**4. Testing External Services**
```python
# Bad: flaky due to network/auth
def test_fetch_real_market_data():
    data = real_api.get_prices()  # Unreliable

# Good: mock the API
def test_process_market_data(mock_broker):
    mock_broker.get_prices.return_value = {...}
    result = my_processor(mock_broker)
    assert result == expected
```

---

## Common Scenarios

### Testing a New Shared Component

1. Create `tests/shared/test_my_component.py`:
```python
import pytest
from shared.my_component import MyComponent

class TestMyComponent:
    def test_basic_case(self):
        obj = MyComponent()
        result = obj.method()
        assert result == expected
    
    def test_error_case(self):
        obj = MyComponent()
        with pytest.raises(ValueError):
            obj.method(invalid_input)
```

2. Add the component to conftest if others need it:
```python
@pytest.fixture
def my_component():
    return MyComponent()
```

### Testing with Mocked Database

```python
def test_saves_to_database(self, mock_db):
    obj = MyClass(db=mock_db)
    obj.save_something()
    
    # Don't check exact SQL, use helper
    assert_helper.assert_portfolio_updated(mock_db)
```

### Testing Async Code

```python
@pytest.mark.asyncio
async def test_async_operation(self):
    result = await my_async_function(data)
    assert result == expected
```

### Testing with Multiple Mocks

```python
def test_multi_broker_execution(self):
    broker1 = AsyncMock()
    broker2 = AsyncMock()
    
    executor = Executor([broker1, broker2])
    
    broker1.fill.return_value = success_fill
    broker2.fill.return_value = error_fill
    
    result = executor.execute(trade)
    assert result.status == "partially_filled"
```

---

## Regression Prevention

### Write Tests When Fixing Bugs

Every bug fix needs a regression test:

```python
def test_circuit_breaker_stays_tripped_until_reset():
    """Regression: Circuit was resetting too early (bug #42)"""
    cb = CircuitBreaker()
    cb.check(portfolio_value=95000, peak_value=100000)  # Trips
    assert cb.is_tripped()
    
    # Even if loss improves, should stay tripped
    is_tripped, _ = cb.check(portfolio_value=98000, peak_value=100000)
    assert is_tripped
    
    # Only reset() should clear it
    cb.reset()
    assert not cb.is_tripped()
```

### Test Matrix for New Features

Before merging, test:

- ✅ Happy path (main use case)
- ✅ Error cases (what can go wrong?)
- ✅ Edge cases (zero, negative, max values)
- ✅ State changes (verify DB updates without brittle checks)
- ✅ Async operations (if applicable)

---

## Code Coverage

Run coverage to find untested code:

```bash
pytest tests/ --cov=shared --cov=gateway --cov-report=html
# Open htmlcov/index.html
```

**Target:** 80%+ coverage on core components

**Not counting toward coverage (safe to skip):**
- Logging statements
- Type annotations (Python 3.9+)
- Optional error messages

---

## CI/CD Integration

Tests run automatically on every push:

```yaml
# .github/workflows/tests.yml
- Run: pytest tests/ -v --tb=short
- Check: Coverage >= 80%
- Report: Results in PR
```

---

## Debugging Failed Tests

### Print Debug Info
```python
def test_something(caplog):
    caplog.set_level(logging.DEBUG)
    obj.method()
    print(caplog.text)  # See logs
```

### Run Single Test with Output
```bash
pytest tests/shared/test_circuit_breaker.py::TestCircuitBreaker::test_circuit_breaks -vv -s
```

### Use pdb Debugger
```python
def test_something():
    obj = MyClass()
    breakpoint()  # Pauses here
    result = obj.method()
    assert result == expected
```

---

## Summary: Adding Features Without Breaking Tests

**For each new feature:**

1. ✅ Write test first (TDD)
2. ✅ Use builders for test data (not fixtures)
3. ✅ Use assertion helpers (not brittle mocks)
4. ✅ Mock external dependencies (DB, APIs, brokers)
5. ✅ Test one thing per test
6. ✅ Clear test names (what → expected)
7. ✅ Add regression test when fixing bugs
8. ✅ Run full suite before merging

**This ensures:**
- No breaking changes to existing code
- New features are well-tested
- Easy to understand what failed and why
- Safe to refactor internals (tests guide you)

---

Built with ❤️ following pytest and TDD best practices.
