#!/usr/bin/env python3
"""
Weekly ML model retraining scheduler.

Runs retrain_models.main() immediately on startup, then again every
RETRAIN_INTERVAL_HOURS hours (default 168 = 1 week).

Usage:
  python scripts/retrain_cron.py               # weekly (every 168h)
  RETRAIN_INTERVAL_HOURS=24 python scripts/retrain_cron.py  # daily
  python scripts/retrain_cron.py --once        # run once and exit (CI/cron)
"""
import asyncio
import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

DEFAULT_INTERVAL_HOURS = int(os.environ.get("RETRAIN_INTERVAL_HOURS", 168))


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


async def main():
    parser = argparse.ArgumentParser(description="ML retraining scheduler")
    parser.add_argument(
        "--once", action="store_true",
        help="Run one retraining cycle and exit (useful for system cron)"
    )
    parser.add_argument(
        "--interval-hours", type=int, default=DEFAULT_INTERVAL_HOURS,
        help="Hours between retraining runs (default: 168 = 1 week)"
    )
    args = parser.parse_args()

    from scripts.retrain_models import main as retrain

    cycle = 0
    while True:
        cycle += 1
        print(f"\n[retrain_cron] Cycle {cycle} starting at {_now_utc()}")
        try:
            await retrain()
        except Exception as exc:
            print(f"[retrain_cron] ERROR: {exc}", file=sys.stderr)

        if args.once:
            print("[retrain_cron] --once flag set, exiting.")
            break

        next_run = args.interval_hours
        print(f"[retrain_cron] Next run in {next_run}h  ({next_run * 3600}s)")
        await asyncio.sleep(next_run * 3600)


if __name__ == "__main__":
    asyncio.run(main())
