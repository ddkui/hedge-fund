#!/usr/bin/env python3
"""
Launches all agent processes. Each agent runs as an independent subprocess.
Add new agents to AGENTS list as they are built in subsequent phases.
"""
import subprocess
import sys
import signal

AGENTS: list[str] = [
    "data/ingest/main.py",
    # Uncomment as agents are built in Phase 4+:
    # "agents/research/main.py",
    # "agents/macro/main.py",
    # "agents/sentiment/main.py",
    # "agents/options/main.py",
    # "agents/portfolio_researcher/main.py",
    # "agents/quant/momentum/main.py",
    # "agents/quant/mean_reversion/main.py",
    # "agents/quant/ml_quant/main.py",
    # "agents/quant/macro_quant/main.py",
    # "agents/quant/supervisor/main.py",
    # "agents/portfolio_mgr/main.py",
    # "agents/risk/main.py",
    # "agents/execution/main.py",
    # "agents/cio/main.py",
    # "agents/ops/main.py",
]

processes: list[subprocess.Popen] = []

def shutdown(signum, frame):
    print("\nShutting down all agents...")
    for p in processes:
        p.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)

if not AGENTS:
    print("No agents configured yet. Uncomment entries in AGENTS list as they are built.")
    sys.exit(0)

for agent_path in AGENTS:
    p = subprocess.Popen([sys.executable, agent_path])
    processes.append(p)
    print(f"Started: {agent_path} (PID {p.pid})")

print(f"Running {len(processes)} agent(s). Press Ctrl+C to stop.")
for p in processes:
    p.wait()
