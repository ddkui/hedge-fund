import json
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from backtest.db import BacktestDB
from backtest.metrics import compute_metrics
from shared.config import settings


class ReportGenerator:
    def __init__(self, db: BacktestDB, run_id: int):
        self._db = db
        self._run_id = run_id
        _templates_dir = Path(__file__).parent / "templates"
        self._env = Environment(loader=FileSystemLoader(str(_templates_dir)))

    async def generate(self, output_path: str) -> dict:
        snapshots = await self._db.fetch(
            "SELECT time, cash, total_value, peak_value FROM portfolio_state ORDER BY time ASC"
        )
        trades = await self._db.fetch(
            "SELECT time, symbol, action, quantity, price, confidence FROM trades ORDER BY time ASC"
        )

        metrics = compute_metrics(snapshots, trades, settings.initial_capital)

        sorted_snaps = sorted(snapshots, key=lambda s: s["time"])
        values = [float(s["total_value"]) for s in sorted_snaps]
        times = [s["time"].isoformat() if hasattr(s["time"], "isoformat") else str(s["time"]) for s in sorted_snaps]

        peak = values[0] if values else 0.0
        drawdown = []
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100.0 if peak > 0 else 0.0
            drawdown.append(round(dd, 4))

        template = self._env.get_template("report.html.j2")
        html = template.render(
            run_id=self._run_id,
            metrics=metrics,
            times=times,
            equity=values,
            drawdown=drawdown,
            trades=trades,
        )

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(html, encoding="utf-8")
        return metrics
