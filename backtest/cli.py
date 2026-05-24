#!/usr/bin/env python3
"""
Backtesting CLI entry point.

Usage:
  python backtest/cli.py \
    --start 2024-01-01 \
    --end   2024-12-31 \
    --step  1h \
    --output reports/backtest_2024.html
"""
import asyncio
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, ".")

DEFAULT_AGENTS = [
    "aggregator",
    "momentum", "mean_reversion", "ml_quant",
    "quant_supervisor",
    "portfolio_mgr", "risk", "execution",
]


def parse_step(step_str: str) -> int:
    step_str = step_str.strip().lower()
    if step_str.endswith("h"):
        return int(step_str[:-1]) * 3600
    if step_str.endswith("m"):
        return int(step_str[:-1]) * 60
    if step_str.endswith("d"):
        return int(step_str[:-1]) * 86400
    if step_str.endswith("s"):
        return int(step_str[:-1])
    raise ValueError(f"Unknown step format: {step_str!r}. Use 1h, 30m, 1d, 3600s.")


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hedge-fund backtesting engine")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--step", default="1h", help="Clock step e.g. 1h, 30m, 1d")
    parser.add_argument(
        "--agents",
        default=",".join(DEFAULT_AGENTS),
        help="Comma-separated agent names",
    )
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--keep-schema", action="store_true", help="Don't drop bt_N schema after run")

    args = parser.parse_args(argv)
    args.start = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc)
    args.end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc)
    args.step_seconds = parse_step(args.step)
    if isinstance(args.agents, str):
        args.agents = [a.strip() for a in args.agents.split(",") if a.strip()]
    return args


async def _main(argv=None):
    import asyncpg
    from shared.config import settings
    from backtest.clock import BacktestClock
    from backtest.bus import InMemoryBus
    from backtest.db import BacktestDB
    from backtest.runner import BacktestRunner
    from backtest.report import ReportGenerator

    args = parse_args(argv)

    # Create backtest_runs entry
    conn = await asyncpg.connect(settings.db_dsn)
    run_id = await conn.fetchval(
        """
        INSERT INTO backtest_runs (start_date, end_date, step_seconds, agents, status)
        VALUES ($1, $2, $3, $4, 'running')
        RETURNING id
        """,
        args.start, args.end, args.step_seconds, args.agents,
    )
    await conn.close()

    print(f"Backtest run ID: {run_id}")
    print(f"Period: {args.start.date()} → {args.end.date()}")
    print(f"Step: {args.step}  Agents: {', '.join(args.agents)}")

    clock = BacktestClock(start=args.start, end=args.end, step_seconds=args.step_seconds)
    print(f"Ticks: {len(clock)}")

    db = BacktestDB(dsn=settings.db_dsn, run_id=run_id)
    bus = InMemoryBus()

    final_status = "failed"
    metrics = None
    try:
        await db.connect()
        await db.create_schema()

        runner = BacktestRunner(
            run_id=run_id, clock=clock, db=db, bus=bus, agent_names=args.agents
        )

        print("Running simulation...")
        await runner.run()

        print("Generating report...")
        gen = ReportGenerator(db=db, run_id=run_id)
        metrics = await gen.generate(args.output)
        final_status = "done"
    finally:
        if not args.keep_schema:
            try:
                await db.drop_schema()
            except Exception:
                pass
        await db.disconnect()

        status_conn = await asyncpg.connect(settings.db_dsn)
        await status_conn.execute(
            "UPDATE backtest_runs SET status = $1 WHERE id = $2", final_status, run_id
        )
        await status_conn.close()

    if metrics:
        print("\n=== Results ===")
        print(f"  Total Return:  {metrics['total_return_pct']:.2f}%")
        print(f"  CAGR:          {metrics['cagr_pct']:.2f}%")
        print(f"  Sharpe Ratio:  {metrics['sharpe_ratio']:.3f}")
        print(f"  Max Drawdown:  {metrics['max_drawdown_pct']:.2f}%")
        print(f"  Total Trades:  {metrics['total_trades']}")
        print(f"  Final Value:   ${metrics['final_value']:,.2f}")
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    asyncio.run(_main())
