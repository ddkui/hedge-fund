import math
from datetime import datetime


def compute_metrics(
    snapshots: list[dict],
    trades: list[dict],
    initial_capital: float,
) -> dict:
    if not snapshots:
        return {
            "total_return_pct": 0.0,
            "cagr_pct": 0.0,
            "sharpe_ratio": 0.0,
            "max_drawdown_pct": 0.0,
            "total_trades": len(trades),
            "final_value": initial_capital,
        }

    sorted_snaps = sorted(snapshots, key=lambda s: s["time"])
    values = [float(s["total_value"]) for s in sorted_snaps]
    final_value = values[-1]

    total_return_pct = (final_value - initial_capital) / initial_capital * 100.0

    start_time: datetime = sorted_snaps[0]["time"]
    end_time: datetime = sorted_snaps[-1]["time"]
    years = (end_time - start_time).total_seconds() / (365.25 * 24 * 3600)
    if years > 0 and final_value > 0:
        cagr_pct = ((final_value / initial_capital) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr_pct = total_return_pct

    # Period returns for Sharpe
    returns = []
    for i in range(1, len(values)):
        if values[i - 1] > 0:
            returns.append((values[i] - values[i - 1]) / values[i - 1])

    if returns and any(r != 0 for r in returns):
        n = len(returns)
        mean_r = sum(returns) / n
        variance = sum((r - mean_r) ** 2 for r in returns) / max(n - 1, 1)
        std_r = math.sqrt(variance) if variance > 0 else 0.0
        if std_r > 0:
            periods_per_year = _estimate_periods_per_year(sorted_snaps)
            sharpe_ratio = (mean_r / std_r) * math.sqrt(periods_per_year)
        else:
            sharpe_ratio = 0.0
    else:
        sharpe_ratio = 0.0

    # Max drawdown
    peak = values[0]
    max_drawdown_pct = 0.0
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak * 100.0
            if dd > max_drawdown_pct:
                max_drawdown_pct = dd

    return {
        "total_return_pct": total_return_pct,
        "cagr_pct": cagr_pct,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown_pct": max_drawdown_pct,
        "total_trades": len(trades),
        "final_value": final_value,
    }


def _estimate_periods_per_year(snapshots: list[dict]) -> float:
    if len(snapshots) < 2:
        return 252.0
    deltas = []
    for i in range(1, min(10, len(snapshots))):
        dt = (snapshots[i]["time"] - snapshots[i - 1]["time"]).total_seconds()
        if dt > 0:
            deltas.append(dt)
    if not deltas:
        return 252.0
    avg_seconds = sum(deltas) / len(deltas)
    return (365.25 * 24 * 3600) / avg_seconds
