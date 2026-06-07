# Local AI Development Guide

This guide explains how to use Claude (or similar AI) to maintain and extend your hedge fund locally.

---

## Overview

You can use Claude Code, GitHub Copilot, or another AI to:
- Fix bugs with regression tests
- Add new features safely
- Maintain compliance
- Write and run tests locally
- Deploy to production with confidence

All changes happen locally first, get reviewed, tested, then pushed to GitHub.

---

## Setup: Local Development Environment

### Prerequisites

```bash
# Required
Python 3.11+          # pip install python@3.11
Git                   # git config user.name "Your Name"
PostgreSQL (Docker)   # docker run -d postgres:latest
Redis (Docker)        # docker run -d redis:latest
Node.js 18+          # npm --version

# Optional but recommended
Docker Desktop       # For Postgres, Redis, Ollama
VS Code              # With Python extension
Ollama               # For local LLM inference
```

### Install Dependencies

```bash
# Clone or navigate to repo
cd ~/hedge-fund

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-asyncio pytest-cov pytest-mock

# Install frontend (optional, if developing dashboard)
cd dashboard && npm install && cd ..
```

### Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit .env with your values
# IMPORTANT: Use test/development values, never production secrets
PAPER_TRADING=true
ALPACA_API_KEY=<test-key>
ALLOWED_LOGIN_EMAILS=your@email.com

# Load environment
export $(cat .env | xargs)
```

### Start Services

```bash
# Terminal 1: PostgreSQL
docker run -d \
  --name timescaledb \
  -e POSTGRES_PASSWORD=changeme \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg14

# Terminal 2: Redis
docker run -d \
  --name redis \
  -p 6379:6379 \
  redis:latest

# Terminal 3: API Server
cd gateway && python main.py
# Runs on http://localhost:8000

# Terminal 4: Dashboard (optional)
cd dashboard && npm run dev
# Runs on http://localhost:3000

# Terminal 5: Ollama (optional, for local LLM)
ollama serve
```

### Verify Setup

```bash
# Check all services running
curl http://localhost:8000/metrics | head -20
# Should return Prometheus metrics

# Check database
psql -h localhost -U hedgefund -d hedgefund -c "SELECT version();"

# Check Redis
redis-cli ping
# Should return PONG

# Run a test
pytest tests/ -v --tb=short
# Should see tests passing
```

---

## Workflow: Using Claude Locally

### Option 1: Claude Code (Recommended)

Claude Code is the official Claude IDE with full tool access.

```bash
# Install Claude Code CLI (if not already installed)
npm install -g @anthropic-ai/claude-code

# Start Claude Code in your project
claude-code

# In Claude Code:
# - Use /list to see files
# - Use /read <file> to read code
# - Use /edit <file> to modify code
# - Use /bash to run commands
# - Use /pytest to run tests
```

**Advantages**:
✅ Full access to tools (read, write, bash, etc.)
✅ Can run tests and see results
✅ Can commit and push directly
✅ Best performance and accuracy

### Option 2: GitHub Copilot

GitHub Copilot offers code completion in your IDE.

```bash
# Install in VS Code
1. Install "GitHub Copilot" extension
2. Sign in with GitHub
3. Start typing to get suggestions
```

**Advantages**:
✅ Real-time code suggestions
✅ Inline help while coding
✅ Free tier available

**Limitations**:
❌ Can't run tests or bash commands
❌ Limited to code completion

### Option 3: ChatGPT with Code Interpreter

Use ChatGPT's code interpreter mode to work with files.

```
1. Open ChatGPT with Code Interpreter
2. Upload your codebase (as zip)
3. Ask questions like "Fix the bug in circuit_breaker.py"
4. Download modified files
5. Copy to your local repo
```

**Advantages**:
✅ Can execute Python directly
✅ Good for data analysis and testing

**Limitations**:
❌ Can't modify files on your system directly
❌ Session-limited context window

---

## Development Workflow

### Step 1: Create Issue (Optional but Recommended)

Create a GitHub issue describing what you want to do:

```markdown
# Add correlation hedging dashboard

## Description
Add a new tab to the dashboard showing:
- Current portfolio correlation to SPY
- Hedge status (active/inactive)
- SPY short quantity
- Hedge history (last 30 days)

## Acceptance Criteria
- [ ] Correlation updated in real-time
- [ ] Shows hedge quantity and P&L
- [ ] Has tests for calculations
- [ ] Compliant with risk limits
```

### Step 2: Create Local Branch

```bash
# Update main branch
git checkout master
git pull origin master

# Create feature branch
git checkout -b feature/correlation-hedging-dashboard

# Now you're on a local branch (won't affect main until merged)
```

### Step 3: Ask Claude to Implement

**Using Claude Code**:
```
"Add a new dashboard component that shows correlation hedging status.
File locations:
- shared/correlation_hedger.py (existing, read first)
- dashboard/app/risk/page.tsx (create new)
- tests/integration/test_hedging_dashboard.py (test)

Requirements:
- Display current SPY correlation
- Show if hedge is active
- Display hedge quantity and P&L
- All values update in real-time
- Write tests first (TDD)
"
```

### Step 4: Claude Writes Code

Claude will:
1. ✅ Read existing code to understand patterns
2. ✅ Write tests first (TDD)
3. ✅ Implement the feature
4. ✅ Run tests to verify
5. ✅ Ask you for approval before committing

```python
# Example: Claude writes this test first
# tests/integration/test_hedging_dashboard.py

def test_correlation_hedge_display(mock_db):
    """Test that correlation hedge status displays correctly."""
    hedger = CorrelationHedger()
    hedger.update_correlation(0.85)
    
    assert hedger.should_hedge()
    # Dashboard reads this and shows "HEDGE ACTIVE"
```

### Step 5: Review & Approve

Claude asks: *"Does this look right? Should I commit and push?"*

You review:
- ✅ Does the code follow existing patterns?
- ✅ Are tests passing?
- ✅ Is it compliant with rules in CLAUDE.md?
- ✅ Does it match what you asked for?

If yes: *"Looks good, commit and push"*  
If no: *"Change X and Y"* → Claude makes changes

### Step 6: Claude Commits & Pushes

```bash
git add tests/integration/test_hedging_dashboard.py dashboard/app/risk/page.tsx
git commit -m "feat: add correlation hedging dashboard tab

- Display current SPY correlation
- Show hedge status (active/inactive)
- Display hedge quantity and P&L
- Real-time updates via WebSocket

All tests passing."

git push origin feature/correlation-hedging-dashboard
```

### Step 7: Create Pull Request

```bash
# GitHub automatically suggests PR based on branch
# You create PR via GitHub UI or:
gh pr create --title "Add correlation hedging dashboard" \
  --body "Displays hedge status and P&L in real-time"
```

### Step 8: Code Review (GitHub)

1. GitHub runs automated tests (via Actions)
2. You review changes
3. You approve or request changes
4. Merge to master when ready

```bash
# Merge and delete branch
git checkout master
git pull origin master
git branch -d feature/correlation-hedging-dashboard
```

---

## Common Tasks with Claude

### Task 1: Fix a Bug

```
Claude: "I found a bug in circuit_breaker.py where the reset() method 
doesn't reset the tripped_at timestamp. Let me write a regression test first."

You: "Sure, write the test and fix it."

Claude: (writes test that fails, fixes code, test passes)
Claude: "Done! All tests pass. Should I commit?"

You: "Yes, push it."
```

### Task 2: Add a New Test

```
Claude: "You want me to add more test coverage for position_sizer.py. 
I'll add tests for edge cases."

Claude: (writes 5 new tests)
Claude: "Added 5 new tests for edge cases. Coverage increased from 82% to 91%."

You: "Commit these."
```

### Task 3: Refactor Code

```
Claude: "The broker_failover.py code has some duplication. 
Can I refactor it to be cleaner?"

Claude: "Sure, I'll refactor while keeping all tests passing."

Claude: (refactors)
Claude: "Refactored! All 47 tests still pass. Should I commit?"

You: "Looks good. Push it."
```

### Task 4: Add Compliance Check

```
Claude: "I can add a compliance check to ensure all trades 
are logged in the audit trail."

You: "Great, make sure it blocks trades if audit fails."

Claude: (writes test, implements check, adds to execution pipeline)
Claude: "Added audit check. Now trades fail-safe if audit logging fails."
```

---

## Testing Locally

### Run All Tests

```bash
# All tests
pytest tests/ -v

# Just unit tests (fast)
pytest tests/shared/ -v

# Just integration tests
pytest tests/integration/ -v

# With coverage report
pytest tests/ --cov=shared --cov=gateway --cov-report=html
open htmlcov/index.html  # View coverage report
```

### Ask Claude to Run Tests

In Claude Code:
```
/bash pytest tests/ -v --tb=short
```

Claude will:
- Run the tests
- Show results
- Highlight failures
- Suggest fixes

### Watch Tests While Developing

```bash
# Terminal: Watch mode
pytest tests/ -v --tb=short --looponfail

# Runs tests continuously as you save files
```

---

## Debugging Locally

### Use Claude to Debug

```
Claude: "The test is failing. Let me add some debug output."

Claude: (adds print statements, runs test again)

Claude: "I see the issue - the portfolio value calculation is wrong. 
Let me fix it..."

Claude: (fixes code, test passes)
```

### Run Single Test with Debug

```bash
# Run one test with verbose output
pytest tests/shared/test_circuit_breaker.py::TestCircuitBreaker::test_trips -vv

# Run with print output visible
pytest tests/shared/test_circuit_breaker.py::TestCircuitBreaker::test_trips -vv -s

# Use pdb debugger
# (Claude can add breakpoints and step through code)
```

### Check Live System

```bash
# View recent trades
curl http://localhost:8000/api/dashboard/trades | jq

# View metrics
curl http://localhost:8000/metrics | grep hf_

# Check database directly
psql -h localhost -U hedgefund -d hedgefund
> SELECT * FROM trades WHERE status != 'executed' LIMIT 5;
```

---

## Compliance While Developing

### Claude Follows These Rules

Claude reads `CLAUDE.md` which enforces:

✅ **Must have tests** for every change  
✅ **Cannot weaken safety** (circuit breaker, risk limits)  
✅ **Cannot hardcode secrets** (must use .env)  
✅ **Must maintain audit trail** (every trade logged)  
✅ **Cannot break existing tests**  

### Example: Claude Refuses Unsafe Changes

```
You: "Remove the circuit breaker limit check to allow more trading."

Claude: "I can't do that. CLAUDE.md says circuit breaker 
limits are critical and can't be weakened without user approval. 
Would you like to increase the limit instead (with tests)?"

You: "OK, increase from 5% to 7%."

Claude: (writes test, updates limit, runs full test suite)
Claude: "Done! Limit increased to 7% with all tests passing."
```

---

## Deployment: Local → Production

### 1. Verify Everything Works Locally

```bash
# All tests pass
pytest tests/ -v --tb=short

# No uncommitted changes
git status
# On branch master
# nothing to commit, working tree clean

# All services running
curl http://localhost:8000/metrics
redis-cli ping
psql -c "SELECT 1"
```

### 2. Push to GitHub

```bash
git push origin master
```

### 3. GitHub Actions Runs CI

```
GitHub Actions:
✅ Runs all tests
✅ Checks code coverage
✅ Builds Docker images (if configured)
✅ Deploys to staging (if configured)
```

### 4. Manual Verification (If Applicable)

```bash
# If you have a staging server
ssh staging.server.com
cd hedge-fund
git pull origin master
pytest tests/ -v
# Start services and verify
```

### 5. Deploy to Production

```bash
# If using Docker
docker-compose up -d

# If using your own infrastructure
git pull && python -m pytest tests/ && python gateway/main.py
```

---

## File Structure for Local Development

```
hedge-fund/
├── CLAUDE.md                    # AI instructions (READ FIRST)
├── docs/
│   ├── COMPLIANCE.md           # Regulatory requirements
│   ├── TESTING.md              # Test patterns
│   └── IMPROVEMENTS_GUIDE.md   # How 10 improvements work
├── shared/                      # Business logic (testable)
│   ├── circuit_breaker.py      # Safety limit
│   ├── trade_audit.py          # Audit trail
│   └── ... (other improvements)
├── gateway/                     # FastAPI app
│   ├── main.py
│   └── routers/
├── tests/                       # TDD tests
│   ├── conftest.py             # Fixtures
│   ├── shared/                 # Unit tests
│   ├── gateway/                # Integration tests
│   └── integration/            # End-to-end tests
├── dashboard/                   # React frontend
├── agents/                      # Analysis agents
├── data/                        # Data ingestion
├── .env.example                # Template
├── requirements.txt            # Python deps
└── .gitignore                  # Never commit secrets
```

---

## Security: Never Commit Secrets

### ❌ NEVER Commit
```
.env              (API keys, passwords)
secrets.json      (credentials)
*.key             (private keys)
config.prod.yaml  (production secrets)
```

### ✅ Always Commit
```
.env.example      (template only)
requirements.txt  (dependencies)
tests/            (test code)
docs/             (documentation)
```

### Claude Knows This

Claude reads `.gitignore` and won't commit secrets.

If you ask: *"Add my Alpaca API key"*

Claude responds: *"I can't commit your API key. Add it to .env instead. 
I can help you set up .env.example as a template."*

---

## Tips for Working with Claude

### 1. Be Specific

❌ *"Fix the trading system"*  
✅ *"Fix the circuit breaker reset bug. Write a test that shows it's broken, 
then fix it. All tests should pass."*

### 2. Provide Context

❌ *"Add a new feature"*  
✅ *"Add a dashboard component for the correlation hedger. 
Read shared/correlation_hedger.py first, then create dashboard/app/risk/page.tsx. 
Use TDD (test first, then component)."*

### 3. Reference Files

```
"In shared/position_sizer.py, the calculate_qty method has a bug.
When account_equity is 0, it should return 0, not divide by zero.
Write a test first to catch this."
```

### 4. Ask Claude to Review

```
"Does this test properly test the circuit breaker?
Is the code following patterns from other components?
Are there any compliance issues I should be aware of?"
```

### 5. Let Claude Suggest Improvements

```
"I want to add X feature. What's the best way to do it
given the existing architecture?"

Claude might suggest:
- Where to add the code
- What tests to write
- How to integrate it
- Potential issues to watch for
```

---

## Troubleshooting

### Issue: Tests Failing Locally

```bash
# Clear caches
rm -rf .pytest_cache
rm -rf __pycache__

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Run tests again
pytest tests/ -v --tb=short
```

### Issue: Import Errors

```bash
# Check Python path
python -c "import sys; print(sys.path)"

# Ensure virtual environment activated
source venv/bin/activate

# Reinstall package
pip install -e .
```

### Issue: Database Connection Failed

```bash
# Check PostgreSQL is running
docker ps | grep timescaledb

# If not running
docker run -d \
  --name timescaledb \
  -e POSTGRES_PASSWORD=changeme \
  -p 5432:5432 \
  timescale/timescaledb:latest-pg14

# Check connection
psql -h localhost -U hedgefund -d hedgefund -c "SELECT 1"
```

### Issue: Claude Can't Run Commands

If Claude says *"I don't have shell access"*:

```
Make sure you're using Claude Code with full tool access.
If using ChatGPT, you need Code Interpreter enabled.
If using Copilot, it only provides code suggestions (can't run commands).
```

---

## Summary

### Local AI Development Workflow

1. **Setup**: Install dependencies, start services
2. **Ask Claude**: Describe what you want
3. **Claude Works**: Reads code, writes tests, implements feature
4. **Review**: Check code, approve changes
5. **Claude Commits**: Tests pass, code pushed to branch
6. **You Test**: Run locally, verify works
7. **Merge**: GitHub PR → master
8. **Deploy**: Automated or manual deployment

### Key Principles

✅ **Tests First** (TDD) - Claude writes test before code  
✅ **Always Safe** - Claude follows CLAUDE.md rules  
✅ **Compliant** - Circuit breaker, audit trail, risk limits always enforced  
✅ **Maintainable** - Code follows patterns, well documented  
✅ **Debuggable** - All decisions logged and auditable  

### Result

You have a hedge fund that:
- Stays compliant automatically
- Can be maintained by AI
- Improves over time
- Is safe to let run autonomously
- Has full audit trail for SEC

---

Ready to develop locally? Start with: `CLAUDE.md`

Built for human + AI collaboration. 🤖 + 👨‍💻
