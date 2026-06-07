# Compliance Framework

This document outlines SEC, FINRA, and state regulations that apply to this AI hedge fund.

---

## Regulatory Overview

### What You Are Running

This is a **registered investment advisor (RIA)** or **hedge fund** that:
- Manages money for investors
- Makes trading decisions (autonomous AI)
- Executes trades across multiple brokers
- Must file SEC Form ADV Part 1 & Part 2
- Must maintain audit trails (SEC Rule 17a-3)
- Must comply with FINRA rules if using stock brokers

---

## Key Compliance Requirements

### 1. SEC Rule 17a-3: Recordkeeping

**REQUIREMENT**: Every trade must be recorded with:
- ✅ Trade date and time (timestamp)
- ✅ Symbol, quantity, action (buy/sell)
- ✅ Execution price
- ✅ Broker and account
- ✅ Reason for trade (e.g., "consensus_score=2.5")
- ✅ Who authorized it (AI + Risk Agent)
- ✅ Settlement details

**HOW WE COMPLY**:
```python
# shared/trade_audit.py - Records everything
record = TradeAuditRecord(
    trade_id=1,
    symbol="AAPL",
    action="long",
    quantity=100,
    consensus_score=2.5,  # Why we traded
    confidence=75.0,      # Confidence level
    regime="expansion",   # Market regime
    agent_signals={...},  # Per-agent scores
    status="executed",
    executed_at=datetime.now(),
    final_price=150.0,
)
audit_log.add_record(record)
```

**RETENTION**: Keep audit trail for minimum 6 years
- Database: TimescaleDB (hypertable on `trades` table)
- Exports: Monthly PDF to S3 + local backup

---

### 2. SEC Rule 17a-4: Trade Confirmation

**REQUIREMENT**: Confirm all trades with clients within 1 business day

**HOW WE COMPLY**:
```python
# gateway/routers/reports.py
async def generate_monthly_report(investor_account):
    """Generate monthly trade confirmation."""
    trades = await query_trades(investor_account, last_month)
    
    # Create PDF with:
    # - All trades executed
    # - Execution prices
    # - Commissions/fees
    # - P&L
    
    pdf = generate_pdf(trades)
    await send_email(investor.email, pdf)  # Monthly confirmation
```

---

### 3. SEC Rule 206(4)-7: Custody Rule

**REQUIREMENT**: Don't hold client money directly; use qualified custodian

**HOW WE COMPLY**:
- ✅ Alpaca (FINRA/SIPC member, SEC-regulated)
- ✅ Interactive Brokers (FINRA/SIPC member, SEC-regulated)
- ✅ Capital.com (UK FCA-regulated, offers US accounts)

**WE DO NOT**: Hold crypto wallets, bank accounts, or any direct custody

```python
# Trades executed directly by brokers
# Money stays in broker accounts
# We execute orders on behalf of investors
```

---

### 4. SEC Rule 17a-1: Net Capital Rule

**REQUIREMENT**: Maintain minimum net capital

**HOW WE COMPLY**:
```python
# Monitor quarterly
quarterly_net_capital = calculate_net_capital()
if quarterly_net_capital < minimum_required:
    alert_compliance_officer()  # Violation alert
    halt_new_trades()           # Stop trading
```

---

### 5. FINRA Rule 4512: Broker-Dealer Registration

**REQUIREMENT**: Brokers handling trades must be registered with FINRA

**HOW WE COMPLY**:
- Alpaca: FINRA member #26635 ✅
- IB: FINRA member #4988 ✅
- Capital.com: Not US FINRA (uses qualified custodians) ✅

```python
# shared/broker_config.py - Only approved brokers allowed
APPROVED_BROKERS = {
    "alpaca": AlpacaBroker,      # FINRA #26635
    "ib": InteractiveBrokersBroker,  # FINRA #4988
    "capital_com": CapitalComBroker,  # FCA-regulated
}
```

---

### 6. SEC Form ADV: Disclosure

**REQUIREMENT**: File Part 1 (registration) and Part 2 (brochure)

**Part 1**: Company info, conflicts of interest, regulatory history
**Part 2**: Investment strategy, fees, risks

**HOW WE COMPLY**:
```yaml
# Create: docs/form_adv_part2.md
- Investment Strategy: AI-driven, multi-broker, regime-aware
- Fees: [Your fee structure]
- Conflicts: Potential conflicts with AI recommendations
- Risk Disclosures: Circuit breaker halts trading at -5% daily loss
- Performance: Backtested results (not guaranteed)
```

**File annually** via SEC EDGAR (Electronic Data Gathering)

---

### 7. SIPC Protection (Investor Protection)

**REQUIREMENT**: Inform investors they have SIPC coverage

**HOW WE COMPLY**:
```markdown
# Investment Disclosure (send to all investors)

## Investor Protection (SIPC)

Your account is protected by SIPC (Securities Investor Protection Corporation):
- Up to $500k per account
- Up to $250k for cash

Coverage includes:
✅ Missing securities
✅ Missing cash from sales

NOT covered:
❌ Market losses
❌ Bad investment decisions

Visit: www.sipc.org for full details
```

---

### 8. Best Execution

**REQUIREMENT**: Execute trades at best available price for clients

**HOW WE COMPLY**:
```python
# shared/volatility_executor.py
# Smart order routing based on market conditions:
# - Low VIX + small order → Market order (fastest)
# - High VIX → Limit order (protection)
# - Large order → VWAP (minimize impact)

# All brokers execute simultaneously
fills = await asyncio.gather(
    alpaca.fill(trade),
    ib.fill(trade),
    capital_com.fill(trade),
)
# Use median price across brokers
```

---

### 9. Anti-Money Laundering (AML)

**REQUIREMENT**: Verify investor identity, monitor suspicious activity

**HOW WE COMPLY**:
```python
# gateway/routers/auth.py
# Google Sign-In with email verification
# ✅ Identity verified by Google (2FA capable)
# ✅ Email allowlist (ALLOWED_LOGIN_EMAILS in .env)
# ✅ All trades logged with timestamp and user

# Monitor: Flag unusual patterns
async def aml_check(trade):
    """Check for suspicious trading patterns."""
    if trade.qty > 100000:  # Unusual size
        alert_compliance()
    if trades_last_24h > 1000:  # Unusual frequency
        alert_compliance()
```

---

### 10. Know Your Customer (KYC)

**REQUIREMENT**: Collect investor information (name, address, income, investment experience)

**HOW WE COMPLY**:
```python
# Implement: gateway/routers/kyc.py
# Collect at account creation:
# ✅ Full legal name
# ✅ Date of birth
# ✅ Address
# ✅ Employment status
# ✅ Net worth / annual income
# ✅ Investment experience

# Store securely (encrypted, separate from trading data)
```

---

### 11. Conflicts of Interest

**REQUIREMENT**: Disclose conflicts and manage them

**CONFLICTS IN THIS SYSTEM**:

| Conflict | Disclosure | Management |
|----------|------------|-----------|
| AI recommends trades | Disclose in ADV Part 2 | Risk Agent + CIO approval |
| Multiple investors on same algorithm | Disclose in ADV Part 2 | Position sizer ensures fair allocation |
| Trading profits benefit AI (in theory) | Disclose in ADV Part 2 | AI not sentient, no personal benefit |
| Using multiple brokers | Disclose in ADV Part 2 | Best execution + failover |

---

### 12. Fiduciary Duty

**REQUIREMENT**: Act in client's best interest (not your own)

**HOW WE COMPLY**:
```python
# Every trade decision must prioritize client returns:
# ✅ Circuit breaker halts losing trades (protects capital)
# ✅ Position sizer limits risk per trade
# ✅ Risk agent approves all trades
# ✅ CIO has veto power
# ✅ Correlation hedger protects against systemic risk
# ✅ Backtesting validates strategy
# ✅ Performance reports show P&L transparently
```

---

## Audit Trail Implementation

### What Gets Logged

```python
# EVERYTHING related to trading decisions

# 1. Signal generation (shared/trade_audit.py)
record = TradeAuditRecord(
    agent_signals={"technical": 0.8, "sentiment": 0.7},  # Per-agent
    consensus_score=1.5,  # How confident
    regime="expansion",   # Market context
)

# 2. Risk checks (gateway/routers/risk.py)
risk_result = {
    "approved": True,
    "reason": "Portfolio drawdown 2.3% < limit 5.0%",
    "checked_at": datetime.now(),
}

# 3. Execution (gateway/routers/trades.py)
fill = {
    "broker": "alpaca",
    "status": "filled",
    "price": 150.0,
    "qty": 100,
    "timestamp": datetime.now(),
}

# 4. Settlement
settlement = {
    "trade_id": 1,
    "broker_settlement_id": "12345",
    "settled_at": datetime.now(),
    "final_price": 150.0,
}
```

### Storage & Retention

```
Database: TimescaleDB
├── trades (main audit table)
├── broker_fills (per-broker fills)
├── signals (what agents recommended)
├── risk_events (what risk agent approved/rejected)
└── optimizer_history (parameter changes)

Backup: S3 (monthly exports, encrypted)
├── 2026-01-trades.parquet
├── 2026-01-signals.parquet
└── 2026-01-risk_events.parquet

Retention: 7 years minimum (SEC requirement)
```

### Audit Reports

```bash
# Export audit trail for SEC examination
async def export_audit_trail(start_date, end_date):
    trades = await query_trades(start_date, end_date)
    fills = await query_broker_fills(start_date, end_date)
    signals = await query_signals(start_date, end_date)
    
    # Create PDF with narrative
    pdf = generate_audit_report(trades, fills, signals)
    # Send to compliance officer or SEC if requested
```

---

## Circuit Breaker Compliance

### Why Circuit Breaker Matters

**Prevents catastrophic losses** that would:
- Violate net capital requirements
- Breach investor agreements
- Force margin calls
- Trigger regulatory investigation

### Current Settings

```python
# shared/circuit_breaker.py
max_loss_pct = 5.0  # Halt trading at -5% daily loss

# This means:
# $100k account → halt at $95k
# $1M account   → halt at $950k
```

### Examples

```
Portfolio value: $100,000
Peak value:     $100,000

Loss tolerance: 5% = $5,000

Scenario 1: Portfolio drops to $97,000
- Loss: 3% ✅ OK, continue trading

Scenario 2: Portfolio drops to $94,000
- Loss: 6% ❌ CIRCUIT BREAKER TRIPS
- All trading halted
- Alert sent to CIO
- Manual review required
```

---

## Regulatory Checklist

### Daily
- [ ] Circuit breaker not tripped (check via dashboard)
- [ ] All trades audited (query trades table)
- [ ] No failed broker connections (Prometheus metrics)
- [ ] No unusual patterns (check AML alerts)

### Weekly
- [ ] Review trade execution quality (best execution report)
- [ ] Check agent performance (win rates by regime)
- [ ] Monitor portfolio concentration (sector/position limits)
- [ ] Verify broker connectivity (failover working)

### Monthly
- [ ] Generate investor reports (PDF with P&L)
- [ ] Export audit trail (backup to S3)
- [ ] Reconcile broker statements (vs our records)
- [ ] Review conflicts of interest (any new ones?)
- [ ] Check net capital (vs minimum required)

### Quarterly
- [ ] File Form ADV-U (updates if major changes)
- [ ] Review performance vs benchmarks
- [ ] Compliance officer reviews audit trail
- [ ] External audit (if required by structure)

### Annually
- [ ] File Form ADV Part 1 (SEC EDGAR)
- [ ] Update Form ADV Part 2 (if strategy changed)
- [ ] Annual compliance review (full audit)
- [ ] Certify books and records (CPA)
- [ ] SIPC payment (if applicable)

---

## Prohibited Activities

### ❌ NEVER DO (Regulatory Violations)

```python
# 1. Trade on insider information
if insider_info_obtained:
    raise ComplianceError("INSIDER TRADING PROHIBITED")

# 2. Manipulate market prices
if artificial_volume_detected:
    raise ComplianceError("MARKET MANIPULATION PROHIBITED")

# 3. Engage in wash trading
if same_trade_bought_and_sold_same_day:
    raise ComplianceError("WASH TRADING PROHIBITED")

# 4. Hold client money directly
if handling_client_cash:
    raise ComplianceError("CUSTODY PROHIBITED - USE BROKER")

# 5. Misrepresent performance
if claimed_returns_exceed_actual:
    raise ComplianceError("FRAUD PROHIBITED")

# 6. Trade without authorization
if not_in_client_agreement:
    raise ComplianceError("UNAUTHORIZED TRADING PROHIBITED")

# 7. Discriminate in account treatment
if investor_A_gets_better_fills_than_B:
    raise ComplianceError("DISCRIMINATION PROHIBITED")
```

---

## Getting Regulatory Approval

### Before Using Live Money

1. **Register as RIA** (if needed)
   - File Form ADV with SEC
   - Obtain CRD number
   - Pass SEC examination

2. **Create Investment Agreement**
   - Outline strategy (what this AI does)
   - Disclose risks
   - Specify fees
   - Get investor signature

3. **Obtain Insurance**
   - Errors & Omissions (E&O) insurance
   - Cyber insurance
   - Fidelity bond (if holding securities)

4. **Set Up Compliance**
   - Designate Compliance Officer
   - Create compliance manual
   - Establish surveillance procedures
   - Document all decisions

5. **Test with Paper Trading**
   - Run 30+ days with paper money
   - Verify all systems work
   - Check audit trail
   - Ensure best execution

6. **Go Live**
   - Start with small amounts
   - Monitor constantly
   - Keep detailed records
   - Report to investors

---

## Reporting to Investors

### Monthly Report (REQUIRED)

```markdown
# Monthly Statement - June 2026

## Performance
- Starting Value: $100,000
- Ending Value: $105,000
- Return: +5.0%
- Sharpe Ratio: 1.5
- Max Drawdown: -3.2%

## Trades Executed
- Total Trades: 24
- Winning: 16 (67%)
- Losing: 8 (33%)
- Largest Win: +$1,230 (AAPL)
- Largest Loss: -$450 (MSFT)

## Risk Metrics
- Portfolio Beta: 1.2
- Correlation to SPY: 0.75
- Volatility: 8.2% (annualized)

## Disclosure
⚠️ Past performance is not indicative of future results
⚠️ AI trading carries inherent risks
⚠️ Circuit breaker halts trading at -5% daily loss
⚠️ See full prospectus for complete disclosure
```

---

## When SEC Might Examine You

### Red Flags That Trigger Examination

- ❌ Unusual trading patterns (high frequency, unusual sizes)
- ❌ Poor performance compared to benchmarks (fraud investigation)
- ❌ Investor complaints (FINRA complaint received)
- ❌ Missing audit trail (record-keeping violation)
- ❌ Broker complaints (best execution issues)
- ❌ Sudden account value changes (potential fraud)

### How to Prepare

```bash
# Keep everything documented
✅ Trade audit trail (6+ years)
✅ Investment agreements (signed by investors)
✅ Performance reports (monthly, verified)
✅ Best execution reports (vs benchmarks)
✅ Risk disclosures (signed acknowledgment)
✅ Compliance certifications (annual)
```

---

## Summary

### Core Compliance Principles

1. **Transparency**: Log everything, hide nothing
2. **Best Execution**: Trade at best available prices
3. **Fiduciary Duty**: Put clients first
4. **Record Keeping**: Keep 6+ years
5. **No Fraud**: Honest reporting always
6. **Segregation**: Client money in broker accounts only
7. **Conflict Management**: Disclose and manage conflicts

### What This System Provides

✅ **Circuit Breaker** - Prevents catastrophic losses  
✅ **Trade Audit** - Every trade logged with reasons  
✅ **Risk Agent** - Reviews all trades before execution  
✅ **CIO Approval** - Human oversight for high-impact trades  
✅ **Best Execution** - Smart order routing  
✅ **Investor Reports** - Monthly P&L and metrics  
✅ **Backtesting** - Validate strategy before live trading  
✅ **Compliance Alerts** - Flag suspicious activity  

### Your Responsibility

- File Form ADV with SEC (if RIA)
- Create investor agreements
- Maintain compliance officer role
- Monitor circuit breaker/risk limits
- Export audit trails regularly
- Respond to investor inquiries
- Report to SEC if required

---

## Contact & Resources

- **SEC**: https://www.sec.gov/info/about.shtml
- **FINRA**: https://www.finra.org
- **SIPC**: https://www.sipc.org
- **OCC (Options)**: https://www.theocc.com

For legal guidance, consult a **securities attorney**.

---

Built to be SEC-compliant from the ground up. 🏛️
