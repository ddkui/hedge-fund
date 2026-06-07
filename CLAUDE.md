# Claude Development Guidelines

This file instructs AI assistants (Claude, etc.) on how to maintain and extend this codebase safely.

---

## Core Principles

**You are maintaining an SEC-regulated AI hedge fund. Every change impacts real money and regulatory compliance.**

1. **Compliance First** - Never sacrifice compliance for features
2. **Tests Required** - Every change needs tests; no exceptions
3. **Transparency** - All decisions (trades, hedges, signals) must be auditable
4. **No Secrets** - No hardcoded credentials, all via environment
5. **No Breaking Changes** - Always extend, never break existing code

---

## What You Can Do Autonomously

✅ **Add new features** following existing patterns  
✅ **Write tests** for any new code  
✅ **Fix bugs** with regression tests  
✅ **Refactor** if tests pass  
✅ **Update documentation**  
✅ **Add compliance checks**  
✅ **Optimize performance** (if tests still pass)  
✅ **Commit and push** (after tests pass)  

## What Requires User Approval

❌ **Cannot change**:
- Broker integration APIs (Alpaca, IB, Capital.com)
- Authentication/authorization logic
- Trade execution logic (without testing extensively)
- Database schema (migrations needed)
- Risk agent approval thresholds
- Circuit breaker limits
- Compliance rules

---

## Before Making Changes

### 1. Read These Files First
```
CLAUDE.md (this file) - Development guidelines
docs/IMPROVEMENTS_GUIDE.md - System architecture
docs/TESTING.md - Test patterns
docs/COMPLIANCE.md - Regulatory rules
shared/circuit_breaker.py - Safety limits
shared/trade_audit.py - Audit trail
```

### 2. Understand the Execution Flow
```
MARKET DATA → ANALYSIS AGENTS → AGGREGATOR 
  ↓
PORTFOLIO MANAGER → TRADE AUDIT → RISK CHECKS
  ↓
EXECUTION (with Circuit Breaker, Failover, Hedging)
  ↓
FILLS → REPORTING
```

### 3. Check Current Test Results
```bash
pytest tests/ -v --tb=short
# All tests must pass before any change
```

---

## Code Organization

### shared/
Core business logic (no dependencies on FastAPI, async, etc.)
- `circuit_breaker.py` - Safety limits (DO NOT MODIFY LIGHTLY)
- `trade_audit.py` - Audit trail (MUST PERSIST ALL TRADES)
- `position_sizer.py` - Position limits (SEC compliance)
- `regime_monitor.py` - Market regime detection
- `agent_memory.py` - Agent performance tracking
- `broker_failover.py` - Redundancy
- `volatility_executor.py` - Order routing
- `backtester.py` - Historical validation
- `correlation_hedger.py` - Risk management
- `investor_report.py` - Reporting

### gateway/
FastAPI application (integrates shared/ logic)
- `routers/auth.py` - Google Sign-In (secure)
- `routers/brokers.py` - Broker management
- `routers/trades.py` - Trade execution
- `routers/risk.py` - Risk agent
- `routers/reports.py` - Investor reports
- `routers/metrics.py` - Prometheus metrics

### dashboard/
React frontend (never contains business logic)

### tests/
TDD patterns (test first, then code)
- `conftest.py` - Fixtures & builders
- `shared/` - Unit tests for shared/
- `gateway/` - Integration tests for routes
- `integration/` - End-to-end tests

### data/
Data ingestion (market data pipelines)

### agents/
Analysis agents (run in separate processes)

---

## Making Changes Safely

### Pattern 1: Add a New Feature

```python
# Step 1: Write test first
# tests/shared/test_my_feature.py
def test_my_feature():
    obj = MyClass()
    result = obj.do_something(input)
    assert result == expected

# Step 2: Implement minimum code to pass
# shared/my_feature.py
class MyClass:
    def do_something(self, input):
        return expected

# Step 3: Run tests
pytest tests/shared/test_my_feature.py -v
# ✅ PASS

# Step 4: Integrate into system
# gateway/routers/some_route.py
from shared.my_feature import MyClass

# Step 5: Commit
git add tests/shared/test_my_feature.py shared/my_feature.py gateway/routers/some_route.py
git commit -m "feat: add my feature"
```

### Pattern 2: Fix a Bug

```python
# Step 1: Write regression test (proves bug exists)
# tests/shared/test_bug.py
def test_bug_is_fixed():
    """Regression test for GitHub issue #123"""
    obj = MyClass()
    result = obj.broken_method()
    assert result == expected  # Currently fails
    
# Step 2: Run test to confirm it fails
pytest tests/shared/test_bug.py -v
# ❌ FAIL (proves bug)

# Step 3: Fix the code
# shared/my_feature.py
def broken_method(self):
    return expected  # Fixed

# Step 4: Run test to confirm it passes
pytest tests/shared/test_bug.py -v
# ✅ PASS

# Step 5: Run full suite to ensure no regressions
pytest tests/ -v
# ✅ ALL PASS

# Step 6: Commit
git commit -m "fix: broken_method returns correct value (issue #123)"
```

### Pattern 3: Refactor Without Breaking Things

```python
# Step 1: Ensure all tests pass
pytest tests/ -v
# ✅ ALL PASS

# Step 2: Refactor internal logic (don't change interface)
# Change implementation, keep function signature the same

# Step 3: Run tests again
pytest tests/ -v
# ✅ ALL PASS (tests should not care about internal changes)

# Step 4: If tests fail, revert refactor
git checkout -- shared/my_feature.py

# Step 5: Commit refactor
git commit -m "refactor: simplify my_feature internal logic"
```

---

## Compliance Rules

### Circuit Breaker (CRITICAL - DO NOT WEAKEN)
```python
# shared/circuit_breaker.py
max_loss_pct = 5.0  # Hard limit: 5% daily loss
# If you want to change this: MUST get user approval
```

**Why**: Regulatory requirement + investor protection

### Trade Audit Trail (CRITICAL - EVERY TRADE LOGGED)
```python
# shared/trade_audit.py
# Every trade must be recorded with:
# ✅ Timestamp
# ✅ Symbol, qty, action
# ✅ Consensus score (how confident)
# ✅ Per-agent contributions
# ✅ Execution price
# ✅ P&L
```

**Why**: SEC Form ADV Part 2 + internal audit trail

### Position Limits (REGULATORY)
```python
# shared/position_sizer.py
max_position_pct = 5.0   # 5% per position
max_sector_pct = 20.0    # 20% per sector
max_leverage = 2.0       # 2x leverage max
```

**Why**: SEC accredited investor rules

### Broker Credentials (NEVER HARDCODED)
```python
# ✅ Good: From .env
api_key = os.getenv("ALPACA_API_KEY")

# ❌ Bad: Hardcoded
api_key = "PK_xyz123"
```

**Why**: Security + auditability

### No Manual Account Access
```python
# ✅ Good: Via API
fill = await broker.fill(trade)

# ❌ Bad: Direct account access
balance = broker.account.cash
```

**Why**: Audit trail + regulatory compliance

---

## Testing Requirements

### Before Committing Any Change

```bash
# 1. Run all tests
pytest tests/ -v --tb=short

# 2. Check coverage
pytest tests/ --cov=shared --cov=gateway --cov-report=term-missing

# 3. If coverage < 80% on changed files: add more tests

# 4. Only then commit
git commit -m "..."
```

### Test Quality Standards

```python
# ✅ Good test
def test_circuit_breaker_trips_at_loss_limit():
    """Clear name: what → expected outcome"""
    cb = CircuitBreaker(max_loss_pct=5.0)
    is_tripped, _ = cb.check(portfolio_value=95000, peak_value=100000)
    assert is_tripped

# ❌ Bad test
def test_cb():
    cb = CircuitBreaker()
    assert cb.check(95000, 100000)[0]  # Unclear what's being tested
```

---

## Deployment Rules

### When Can You Push?

✅ **Always safe to push**:
- Passing tests
- No breaking changes
- New features (if tested)
- Bug fixes (with regression test)
- Documentation updates

❌ **Never push**:
- Failing tests
- Breaking changes
- Credential changes
- Security vulnerabilities

### Deployment Process

```bash
# 1. Ensure tests pass locally
pytest tests/ -v

# 2. Ensure no uncommitted changes
git status
# On branch master
# nothing to commit, working tree clean

# 3. Push
git push origin master

# 4. GitHub Actions runs CI (tests again)

# 5. Monitor Grafana dashboard for issues
# http://localhost:3001
```

---

## Extending the System

### Adding a New Improvement

Use existing patterns from the 10 improvements:

```
1. Create module: shared/my_improvement.py
2. Create tests: tests/shared/test_my_improvement.py
3. Write test first (TDD)
4. Implement code
5. Integrate: Add to execution flow (gateway/routers/)
6. Add API endpoint if needed: gateway/routers/endpoint.py
7. Update docs: docs/IMPROVEMENTS_GUIDE.md
8. Commit & push
```

### Adding a New API Endpoint

```python
# gateway/routers/new_endpoint.py
from fastapi import APIRouter, HTTPException
from shared.my_feature import MyClass

router = APIRouter()

@router.get("/api/new-endpoint")
async def get_something():
    """Get something."""
    try:
        result = MyClass().do_something()
        return {"status": "ok", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Adding a New Agent

```
agents/my_agent/
├── main.py           # Agent logic
├── config.yaml       # Settings
├── models.py         # Pydantic models
└── requirements.txt  # Dependencies
```

---

## Performance Guidelines

### What to Optimize
✅ Database queries (add indexes if needed)
✅ API response times (cache results)
✅ Signal calculation (vectorize with numpy)
✅ Broker API calls (batch requests)

### What NOT to Optimize
❌ Audit logging (always log, never skip for speed)
❌ Risk checks (always check, never skip)
❌ Circuit breaker checks (always check, never skip)

---

## Security Guidelines

### Secrets Management
```python
# ✅ Good
api_key = os.getenv("ALPACA_API_KEY")
if not api_key:
    raise ValueError("ALPACA_API_KEY not set")

# ❌ Bad
api_key = os.getenv("ALPACA_API_KEY", "pk_test_xyz")  # Default exposed!
```

### Input Validation
```python
# ✅ Good
def place_order(qty: float):
    if qty <= 0:
        raise ValueError("qty must be positive")
    if qty > 10000:
        raise ValueError("qty exceeds max")
    # Process order

# ❌ Bad
def place_order(qty: float):
    # Process order without validation
```

### Log Security
```python
# ✅ Good: Mask secrets
secret = "pk_live_abc123xyz"
masked = "****" + secret[-4:]  # Output: ****xyz

# ❌ Bad: Log full secret
logger.info(f"Using API key: {api_key}")  # Leaks credential!
```

---

## Debugging

### When Tests Fail

```bash
# 1. Run failing test with verbose output
pytest tests/shared/test_something.py::test_case -vv

# 2. Add print statements or use pdb
def test_something():
    result = my_function()
    print(f"Result: {result}")  # Debug output
    assert result == expected

# 3. Run with output visible
pytest tests/shared/test_something.py -vv -s

# 4. Use debugger
def test_something():
    result = my_function()
    breakpoint()  # Pauses here
    assert result == expected
```

### When Live Trading Fails

```bash
# 1. Check circuit breaker
grep "tripped" logs/  # See if circuit breaker halted trading

# 2. Check broker fills
sqlite> SELECT * FROM broker_fills ORDER BY created_at DESC LIMIT 10;

# 3. Check trade audit
sqlite> SELECT * FROM trades WHERE status != 'executed' ORDER BY created_at DESC;

# 4. Check Prometheus metrics
curl http://localhost:8000/metrics | grep hf_
```

---

## When to Ask for User Input

❌ **Cannot decide alone** - ask user:
- Changing circuit breaker limits
- Changing broker integrations
- Changing risk thresholds
- Removing features
- Major refactoring that might break things
- Any compliance-related decision

**How to ask**: Create a GitHub issue with:
1. What you want to do
2. Why you want to do it
3. Risks/tradeoffs
4. Your recommendation

---

## Quick Reference

### Run Tests
```bash
pytest tests/ -v
```

### Check Coverage
```bash
pytest tests/ --cov=shared --cov-report=term-missing
```

### Run Single Test
```bash
pytest tests/shared/test_circuit_breaker.py::TestCircuitBreaker::test_trips -v
```

### Start Development Server
```bash
cd gateway && python main.py
```

### Check Compliance
```bash
# Search for hardcoded secrets
grep -r "api_key\s*=" shared/ gateway/ agents/

# Ensure all trades audited
grep -r "audit_log.add_record" gateway/
```

### View Recent Changes
```bash
git log --oneline -10
git diff HEAD~1..HEAD
```

---

## Summary

**You are building an SEC-compliant, AI-managed hedge fund.**

Every change should:
1. ✅ Have tests
2. ✅ Follow existing patterns
3. ✅ Maintain audit trails
4. ✅ Respect risk limits
5. ✅ Stay compliant

**Your job is to**:
- Add features safely
- Fix bugs with regression tests
- Keep code maintainable
- Keep documentation updated
- Ask for approval when unsure

**Trust but verify**: Tests prevent mistakes. Run them before every commit.

---

Questions? Check:
- `docs/TESTING.md` - How to write tests
- `docs/IMPROVEMENTS_GUIDE.md` - System architecture
- `docs/COMPLIANCE.md` - Regulatory rules
- `tests/` - Examples of well-written tests

Good luck maintaining this system! 🚀
