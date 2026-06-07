# Phase 4: Compliance & Reporting Guide

## Overview

Phase 4 provides four critical compliance and regulatory reporting features for SEC-regulated hedge funds:

1. **Compliance Checker** - Pre-trade validation (SEC rules, PDT, position limits)
2. **Tax Calculator** - Capital gains tracking with wash-sale detection
3. **Tax Reporter** - Schedule D generation for IRS filings
4. **13F Filing Generator** - Quarterly SEC Form 13F submission
5. **Audit Exporter** - Complete trade audit trails (CSV/PDF)

All modules work together to ensure regulatory compliance and provide audit-ready reporting.

---

## Installation

### Dependencies

```bash
pip install reportlab  # Required for PDF audit export
```

### Project Setup

```bash
# Clone repository
git clone https://github.com/yourusername/hedge-fund
cd hedge-fund

# Install all dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

---

## Feature 1: Compliance Checker

### Overview

Pre-trade validation against SEC regulations, PDT rules, and position limits.

### Usage Example

```python
from shared.compliance_checker import ComplianceChecker

# Initialize checker
compliance = ComplianceChecker(
    max_position_pct=0.25,           # Max 25% per position
    pdt_min_account_value=25000.0    # PDT minimum account value
)

# Check a trade before execution
result = compliance.check_trade(
    symbol="AAPL",
    quantity=100,
    price=150.0,
    action="BUY",
    portfolio_value=100000.0,
    current_position_qty=0,
    broker_limits={},
    day_trades_today=0,
    last_short_price=None
)

# Handle result
if result.passes:
    print("✅ Trade approved, execute now")
else:
    print(f"❌ Violations: {result.violations}")
    for warning in result.warnings:
        print(f"⚠️  {warning}")
```

### Rules Enforced

#### Rule 1: Position Size Limit (25% per position)
Prevents over-concentration in a single position.

```python
# Example: Portfolio $100k, max position = $25k
# Buying 200 shares @ $150 = $30k (violates limit)
result = compliance.check_trade(
    symbol="AAPL",
    quantity=200,
    price=150.0,
    action="BUY",
    portfolio_value=100000.0,
    current_position_qty=0,
    broker_limits={}
)
assert result.passes is False
assert "position_limit" in result.violations
```

#### Rule 2: Pattern Day Trader (PDT) Rule
Enforces PDT rule: accounts < $25k cannot make 4+ day trades per 5 business days.

```python
# Small account ($10k) with 3 day trades already made
result = compliance.check_trade(
    symbol="AAPL",
    quantity=10,
    price=150.0,
    action="BUY",
    portfolio_value=10000.0,        # Below PDT minimum
    current_position_qty=0,
    broker_limits={},
    day_trades_today=3              # 4th day trade blocked!
)
assert result.passes is False
assert "pdt_violation" in result.violations
```

#### Rule 3: Short-Sale Uptick Rule
Can't short below the last price (SEC Reg SHO requirement).

```python
# Attempting to short below last price
result = compliance.check_trade(
    symbol="XYZ",
    quantity=50,
    price=99.0,                     # Below last short price
    action="SELL",                  # Going short
    portfolio_value=100000.0,
    current_position_qty=0,         # Opening new short
    broker_limits={},
    last_short_price=100.0          # Last price was $100
)
assert result.passes is False
assert "short_sale_uptick" in result.violations
```

#### Rule 4: Concentration Warning
Warns when position exceeds 15% of portfolio (not blocked, but flagged).

```python
# Position at 18% of portfolio
result = compliance.check_trade(
    symbol="MSFT",
    quantity=120,
    price=150.0,
    action="BUY",
    portfolio_value=100000.0,
    current_position_qty=0
)
assert result.passes is True                      # Still approved
assert "concentration_warning" in result.warnings  # But warned
```

### API Endpoints

```python
# GET /api/compliance/check-trade
# POST body:
{
    "symbol": "AAPL",
    "quantity": 100,
    "price": 150.0,
    "action": "BUY",
    "portfolio_value": 100000.0,
    "current_position_qty": 0,
    "day_trades_today": 1
}

# Response:
{
    "passes": true,
    "violations": [],
    "warnings": ["concentration_warning"],
    "max_allowed_notional": 25000.0,
    "pdt_day_trades": 2
}
```

---

## Feature 2: Tax Calculator

### Overview

Tracks tax lots and calculates capital gains with automatic wash-sale detection.

### Usage Example

```python
from shared.tax_calculator import TaxCalculator
from datetime import datetime, timezone

# Initialize calculator (FIFO method)
tax = TaxCalculator(method="FIFO")

# Add purchase lots
buy_date = datetime(2024, 1, 15, tzinfo=timezone.utc)
tax.add_lot(
    symbol="TSLA",
    quantity=100,
    price=100.0,
    purchase_date=buy_date
)

# Record a sale
sale_date = datetime(2024, 6, 15, tzinfo=timezone.utc)
tax.record_sale(
    symbol="TSLA",
    quantity=100,
    sale_price=120.0,
    sale_date=sale_date
)

# Calculate gain on sale
gain = tax.calculate_gain_on_sale("TSLA", 100, 120.0)
print(f"Gain: ${gain}")  # Output: Gain: $2000.0

# Detect wash sale on repurchase
repurchase_date = datetime(2024, 2, 1, tzinfo=timezone.utc)
wash_sale = tax.detect_wash_sale("TSLA", 100, repurchase_date)
if wash_sale.is_wash_sale:
    print(f"Disallowed loss: ${wash_sale.disallowed_loss}")
```

### Cost Basis Methods

Supports three methods for determining which lots to sell:

1. **FIFO** (First-In, First-Out) - Default, most common
2. **LIFO** (Last-In, First-Out)
3. **AVERAGE** (Weighted Average Cost)

```python
# Initialize with different method
tax_fifo = TaxCalculator(method="FIFO")
tax_lifo = TaxCalculator(method="LIFO")
tax_avg = TaxCalculator(method="AVERAGE")
```

### Wash-Sale Detection

Automatically detects wash sales: repurchases within 30 days of loss sales.

```python
# Scenario: Buy $100 → Sell $80 (loss) → Rebuy within 30 days
tax = TaxCalculator()

# Purchase
tax.add_lot("ABC", 100, 100.0, datetime(2024, 1, 1, tzinfo=timezone.utc))

# Loss sale
tax.record_sale("ABC", 100, 80.0, datetime(2024, 2, 1, tzinfo=timezone.utc))

# Repurchase within 30 days (WASH SALE!)
repurchase = datetime(2024, 2, 15, tzinfo=timezone.utc)
wash = tax.detect_wash_sale("ABC", 100, repurchase)

assert wash.is_wash_sale is True
assert wash.disallowed_loss == -2000.0  # $20 loss × 100 shares
assert "30 days" in wash.reason
```

### API Endpoints

```python
# POST /api/taxes/add-lot
{
    "symbol": "AAPL",
    "quantity": 100,
    "price": 150.0,
    "purchase_date": "2024-01-15T00:00:00Z"
}

# POST /api/taxes/record-sale
{
    "symbol": "AAPL",
    "quantity": 100,
    "sale_price": 160.0,
    "sale_date": "2024-06-15T00:00:00Z"
}

# GET /api/taxes/wash-sale-check?symbol=AAPL&quantity=100&date=2024-02-15
{
    "is_wash_sale": true,
    "disallowed_loss": -2000.0,
    "reason": "Purchase within 30 days of 2024-02-01 loss sale"
}
```

---

## Feature 3: Tax Reporter

### Overview

Generates IRS Schedule D tax reports with short-term and long-term capital gains.

### Usage Example

```python
from shared.tax_calculator import TaxCalculator
from shared.tax_reporter import TaxReporter

# Setup and add trades
tax = TaxCalculator()
# ... add lots and record sales ...

# Generate Schedule D report
reporter = TaxReporter(tax)
schedule_d = reporter.generate_schedule_d()

# Access results
print(f"Short-term gains: ${schedule_d['part_i_total_gain']}")
print(f"Long-term gains: ${schedule_d['part_ii_total_gain']}")
print(f"Total: ${schedule_d['total_gain']}")

# Export as CSV for tax preparer
csv = reporter.export_schedule_d_csv()
with open("schedule_d.csv", "w") as f:
    f.write(csv)
```

### Schedule D Format

```
Part I - Short-Term Capital Gains (< 1 year holding)
SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN
AAPL,100,15000.0,15500.0,500.0
MSFT,50,9000.0,9400.0,400.0
Part I Total,,,, 900.0

Part II - Long-Term Capital Gains (>= 1 year holding)
SYMBOL,QUANTITY,COST_BASIS,PROCEEDS,GAIN
TSLA,10,10000.0,12000.0,2000.0
Part II Total,,,, 2000.0

Grand Total,,,, 2900.0
```

### Tax Classification

Holds >= 365 days = long-term (lower tax rate)
Holds < 365 days = short-term (ordinary income rates)

```python
# Classify a gain
classification = reporter.calculator.classify_gain(
    symbol="AAPL",
    purchase_date=datetime(2023, 1, 1, tzinfo=timezone.utc),
    sale_date=datetime(2024, 6, 1, tzinfo=timezone.utc)
)
print(classification)  # Output: "long_term"
```

### API Endpoints

```python
# GET /api/taxes/schedule-d
{
    "part_i_short_term": [...],
    "part_ii_long_term": [...],
    "part_i_total_gain": 900.0,
    "part_ii_total_gain": 2000.0,
    "total_gain": 2900.0
}

# GET /api/taxes/schedule-d/csv
# Returns CSV file with Schedule D data

# GET /api/taxes/schedule-d/pdf
# Returns PDF with formatted Schedule D report
```

---

## Feature 4: Form 13F Filing

### Overview

Generates SEC Form 13F quarterly filings for institutional holdings.

### Usage Example

```python
from shared.form13f_generator import Form13FGenerator

# Initialize with filing info
form13f = Form13FGenerator(
    cik="0001234567",          # Your fund's CIK
    fund_name="My Hedge Fund",
    fiscal_quarter="Q2",
    fiscal_year=2024
)

# Add positions
form13f.add_position(
    symbol="AAPL",
    quantity=1000,
    market_value=150000.0,
    price_per_share=150.0,
    cusip="037833100"
)

form13f.add_position(
    symbol="MSFT",
    quantity=500,
    market_value=180000.0,
    price_per_share=360.0,
    cusip="594918104"
)

# Generate filing
filing = form13f.generate_filing()
print(f"Total positions: {filing['position_count']}")
print(f"Total value: ${filing['total_value']}")

# Export as CSV
csv = form13f.export_csv()
with open("form_13f.csv", "w") as f:
    f.write(csv)
```

### 13F Quarterly Schedule

- **Q1**: Period ended 03-31
- **Q2**: Period ended 06-30
- **Q3**: Period ended 09-30
- **Q4**: Period ended 12-31

Filings due 45 days after quarter end (e.g., Q1 due by 5/15).

### CSV Export Format

```
CUSIP,SYMBOL,QUANTITY,PRICE_PER_SHARE,MARKET_VALUE
037833100,AAPL,1000,150.0,150000.0
594918104,MSFT,500,360.0,180000.0
```

### Position Aggregation

Duplicate positions automatically aggregate:

```python
form13f = Form13FGenerator("0001234567", "Fund", "Q2", 2024)

# Add first AAPL position
form13f.add_position("AAPL", 500, 75000.0, 150.0, "037833100")

# Add second AAPL position (will aggregate)
form13f.add_position("AAPL", 300, 45000.0, 150.0, "037833100")

# Result: 800 shares total, $120k market value
filing = form13f.generate_filing()
assert filing["position_count"] == 1  # Only one AAPL position
assert filing["positions"][0].quantity == 800
assert filing["positions"][0].market_value == 120000.0
```

### API Endpoints

```python
# POST /api/filings/13f/add-position
{
    "symbol": "AAPL",
    "quantity": 1000,
    "market_value": 150000.0,
    "price_per_share": 150.0,
    "cusip": "037833100"
}

# GET /api/filings/13f/filing
{
    "cik": "0001234567",
    "fund_name": "My Fund",
    "period_ended": "2024-06-30",
    "fiscal_quarter": "Q2",
    "fiscal_year": 2024,
    "positions": [...],
    "total_value": 330000.0,
    "position_count": 3
}

# GET /api/filings/13f/csv
# Returns CSV file with Form 13F positions
```

---

## Feature 5: Audit Exporter

### Overview

Generates complete trade audit trails in CSV and PDF formats with compliance decisions.

### Usage Example

```python
from shared.audit_exporter import AuditExporter, TradeAuditRecord
from datetime import datetime, timezone

# Initialize exporter
audit = AuditExporter()

# Add trade record
record = TradeAuditRecord(
    trade_id="TRD001",
    symbol="AAPL",
    action="BUY",
    quantity=100,
    price=150.0,
    executed_at=datetime.now(timezone.utc),
    agent_signals=[
        "technical:bullish:0.85",
        "momentum:bullish:0.75"
    ],
    consensus_score=0.80,
    risk_check_passed=True,
    cio_approval_required=False,
    execution_notes="Automated execution via consensus"
)
audit.add_record(record)

# Export as CSV
csv = audit.export_csv()
with open("audit_trail.csv", "w") as f:
    f.write(csv)

# Export as PDF
pdf = audit.export_pdf()
with open("audit_trail.pdf", "wb") as f:
    f.write(pdf)
```

### CSV Format

```
trade_id,symbol,action,quantity,price,executed_at,agent_signals,consensus_score,risk_check_passed,cio_approval_required,execution_notes

TRD001,AAPL,BUY,100,150.0,2024-06-15T10:30:00Z,"technical:bullish:0.85|momentum:bullish:0.75",0.80,true,false,"Automated execution"
TRD002,MSFT,SELL,50,360.0,2024-06-15T11:00:00Z,"technical:bearish:0.70",0.70,true,false,"Profit taking"
```

### PDF Report

The PDF includes:

1. **Summary Table**
   - Trade ID, Symbol, Action, Quantity, Price
   - Execution Time, Consensus Score
   - Risk Status, Agent Signals

2. **Detailed Trade Trail**
   - Per-trade decision audit
   - Agent signals and reasoning
   - Risk checks performed
   - CIO approval status

### Audit Record Fields

| Field | Description |
|-------|-------------|
| `trade_id` | Unique identifier (e.g., TRD001) |
| `symbol` | Stock symbol (e.g., AAPL) |
| `action` | BUY or SELL |
| `quantity` | Number of shares |
| `price` | Execution price |
| `executed_at` | Timestamp with timezone |
| `agent_signals` | List of agent decisions |
| `consensus_score` | 0.0-1.0 confidence level |
| `risk_check_passed` | Boolean approval |
| `cio_approval_required` | CIO involvement flag |
| `execution_notes` | Text notes |

### API Endpoints

```python
# POST /api/audit/add-record
{
    "trade_id": "TRD001",
    "symbol": "AAPL",
    "action": "BUY",
    "quantity": 100,
    "price": 150.0,
    "executed_at": "2024-06-15T10:30:00Z",
    "agent_signals": ["technical:bullish:0.85"],
    "consensus_score": 0.80,
    "risk_check_passed": true,
    "cio_approval_required": false,
    "execution_notes": "Automated execution"
}

# GET /api/audit/export-csv
# Returns CSV file with all audit records

# GET /api/audit/export-pdf
# Returns PDF file with formatted audit trail
```

---

## Tax Reporting Workflow

### End-of-Quarter Process

1. **Collect all sales data** from trading system
   ```python
   sales = get_all_sales(start_date, end_date)
   ```

2. **Record sales in TaxCalculator**
   ```python
   tax = TaxCalculator(method="FIFO")
   for sale in sales:
       tax.record_sale(sale.symbol, sale.qty, sale.price, sale.date)
   ```

3. **Check for wash sales**
   ```python
   for sale in sales:
       wash = tax.detect_wash_sale(sale.symbol, sale.qty, sale.date)
       if wash.is_wash_sale:
           log_compliance_event("WASH_SALE_DETECTED", wash)
   ```

4. **Generate Schedule D**
   ```python
   reporter = TaxReporter(tax)
   schedule_d = reporter.generate_schedule_d()
   ```

5. **Send to tax preparer**
   ```python
   csv = reporter.export_schedule_d_csv()
   send_to_tax_preparer(csv)
   ```

### Year-End Reporting

```bash
# Generate all tax reports
pytest tests/ -v  # Verify compliance

# Export Schedule D
python -c "
from shared.tax_calculator import TaxCalculator
from shared.tax_reporter import TaxReporter

tax = TaxCalculator()
# ... populate with sales ...

reporter = TaxReporter(tax)
pdf = reporter.export_schedule_d_pdf()

with open('schedule_d_2024.pdf', 'wb') as f:
    f.write(pdf)
"
```

---

## 13F Filing Workflow

### Quarterly Process (45 days after quarter end)

1. **Collect holdings at period end**
   ```python
   holdings = get_portfolio_at_date(quarter_end_date)
   ```

2. **Create 13F filing**
   ```python
   form13f = Form13FGenerator(
       cik=my_cik,
       fund_name=my_fund_name,
       fiscal_quarter=quarter,
       fiscal_year=year
   )
   ```

3. **Add all positions**
   ```python
   for holding in holdings:
       form13f.add_position(
           symbol=holding.symbol,
           quantity=holding.qty,
           market_value=holding.value,
           price_per_share=holding.price,
           cusip=holding.cusip
       )
   ```

4. **Generate filing**
   ```python
   filing = form13f.generate_filing()
   assert filing["total_value"] > 100_000_000  # SEC requirement
   ```

5. **Export and submit to SEC**
   ```python
   csv = form13f.export_csv()
   submit_to_sec_edgar(csv, filing)
   ```

### Validation

- Total portfolio value > $100M (SEC requirement)
- All positions have valid CUSIP codes
- No duplicate symbols in filing
- All required fields present

---

## Audit Trail Workflow

### Trade Execution

1. **Record trade decision**
   ```python
   record = TradeAuditRecord(
       trade_id=generate_trade_id(),
       symbol=trade.symbol,
       action=trade.action,
       quantity=trade.qty,
       price=trade.price,
       executed_at=datetime.now(timezone.utc),
       agent_signals=get_agent_signals(),
       consensus_score=calculate_consensus(),
       risk_check_passed=perform_risk_check(),
       cio_approval_required=check_if_escalated(),
       execution_notes=get_notes()
   )
   audit.add_record(record)
   ```

2. **Export for compliance review**
   ```python
   csv = audit.export_csv()
   pdf = audit.export_pdf()
   
   # Archive for SEC audits
   archive.save(csv, f"audit_trail_{quarter}.csv")
   archive.save(pdf, f"audit_trail_{quarter}.pdf")
   ```

### Compliance Audit

```bash
# Monthly audit report
python -c "
from shared.audit_exporter import AuditExporter

audit = AuditExporter()
# ... load all trades ...

pdf = audit.export_pdf()
csv = audit.export_csv()

print(f'Exported {len(audit.records)} trades')
print(f'PDF size: {len(pdf)} bytes')
print(f'CSV lines: {len(csv.splitlines())}')
"
```

---

## Testing Strategy

### Unit Tests

Test each module independently:

```bash
# Compliance tests
pytest tests/shared/test_compliance_checker.py -v

# Tax tests
pytest tests/shared/test_tax_calculator.py -v
pytest tests/shared/test_tax_reporter.py -v

# 13F tests
pytest tests/shared/test_form13f_generator.py -v

# Audit tests
pytest tests/shared/test_audit_exporter.py -v
```

### Integration Tests

Test Phase 4 end-to-end:

```bash
# Run all integration tests
pytest tests/test_phase4_integration.py -v

# Expected output:
# test_full_compliance_and_reporting_flow PASSED
# test_wash_sale_disallows_loss PASSED
# test_pdt_rule_blocks_fourth_day_trade PASSED
```

### Full Test Suite

```bash
# All tests (Phases 1-4)
pytest tests/ -v --tb=short

# Coverage report
pytest tests/ --cov=shared --cov-report=html
```

---

## Compliance Checklist

Before production use:

- [ ] All Phase 4 tests passing (130+)
- [ ] PDT rule enforcement verified
- [ ] Wash-sale detection working
- [ ] Schedule D generation tested
- [ ] 13F filing format validated
- [ ] Audit trail exports verified
- [ ] reportlab installed (`pip install reportlab`)
- [ ] Tax preparer tested with Schedule D CSV
- [ ] SEC EDGAR system tested with 13F format
- [ ] Compliance review completed

---

## Error Handling

### Common Errors

**"portfolio_value must be positive"**
```python
# Fix: Ensure portfolio value is > 0
assert portfolio_value > 0
```

**"quantity must be non-negative"**
```python
# Fix: Quantity should be >= 0
assert quantity >= 0
```

**"action must be BUY or SELL"**
```python
# Fix: Use exact strings
assert action in ("BUY", "SELL")
```

**"No reportlab module"**
```bash
# Install: pip install reportlab
pip install reportlab
```

---

## Best Practices

1. **Always check compliance before trade execution**
   ```python
   result = compliance.check_trade(...)
   if not result.passes:
       return reject_trade(result.violations)
   execute_trade()
   ```

2. **Track all trades in audit trail immediately**
   ```python
   record = TradeAuditRecord(...)
   audit.add_record(record)
   ```

3. **Review wash sales monthly**
   ```python
   for sale in recent_sales:
       wash = tax.detect_wash_sale(...)
       if wash.is_wash_sale:
           notify_tax_preparer(wash)
   ```

4. **Validate 13F before submission**
   ```python
   filing = form13f.generate_filing()
   assert filing["total_value"] > 100_000_000
   assert filing["position_count"] > 0
   ```

5. **Archive audit trails quarterly**
   ```python
   audit_csv = audit.export_csv()
   audit_pdf = audit.export_pdf()
   # Save to secure archive
   ```

---

## Support

For issues or questions:

1. Check test files for usage examples
2. Review CLAUDE.md for development guidelines
3. Run tests: `pytest tests/ -v`
4. Check error messages in violation/warning lists

---

## Summary

Phase 4 provides production-ready compliance and reporting for SEC-regulated hedge funds:

- **Compliance Checker**: Pre-trade validation (SEC, PDT, position limits)
- **Tax Calculator**: Capital gains with wash-sale detection
- **Tax Reporter**: Schedule D generation for IRS
- **13F Filing**: SEC quarterly position reporting
- **Audit Exporter**: Complete CSV/PDF audit trails

All features tested, documented, and ready for regulatory compliance.
