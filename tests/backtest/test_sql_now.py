import re
import pytest
from pathlib import Path

AGENT_FILES = [
    "agents/technical/agent.py",
    "agents/sentiment/agent.py",
    "agents/macro/agent.py",
    "agents/research/agent.py",
    "agents/aggregator/agent.py",
    "agents/quant/momentum/agent.py",
    "agents/quant/mean_reversion/agent.py",
    "agents/quant/ml_quant/agent.py",
    "agents/quant/supervisor/agent.py",
    "agents/portfolio_mgr/agent.py",
    "agents/risk/checker.py",
    "agents/risk/agent.py",
    "agents/cio/agent.py",
]

SQL_NOW_PATTERN = re.compile(r'\bNOW\(\)', re.IGNORECASE)

def test_no_raw_now_in_agent_sql():
    """All agent SQL strings must use now_or_backtest() instead of NOW()."""
    violations = []
    for path in AGENT_FILES:
        content = Path(path).read_text()
        lines = content.splitlines()
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if SQL_NOW_PATTERN.search(line):
                violations.append(f"{path}:{i}: {line.strip()}")
    assert not violations, "Raw NOW() found in agent SQL:\n" + "\n".join(violations)
