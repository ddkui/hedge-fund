# agents/optimizer/alpha_monitor.py
"""
AlphaMonitor — runs daily. Computes beta, Jensen's Alpha, and Sharpe against SPY,
classifies into learning / alpha_achieved / exceptional_alpha tiers, locks params
and emails on tier transitions, and snapshots exceptional strategies to Obsidian.
"""
import math
from datetime import datetime, timezone
from shared.agent_base import BaseAgent
from shared.memory import MemoryMixin


def _daily_returns(values: list[float]) -> list[float]:
    return [(values[i] - values[i - 1]) / values[i - 1]
            for i in range(1, len(values)) if values[i - 1] != 0]


def _compute_sharpe(daily_returns: list[float]) -> float:
    if len(daily_returns) < 2:
        return 0.0
    mean = sum(daily_returns) / len(daily_returns)
    std = math.sqrt(sum((r - mean) ** 2 for r in daily_returns) / (len(daily_returns) - 1))
    return (mean / std) * math.sqrt(252) if std > 0 else 0.0


def _compute_beta(portfolio_values: list[float], spy_values: list[float]) -> float:
    port_ret = _daily_returns(portfolio_values)
    spy_ret = _daily_returns(spy_values)
    n = min(len(port_ret), len(spy_ret))
    if n < 2:
        return 1.0
    port_ret, spy_ret = port_ret[-n:], spy_ret[-n:]
    mean_p = sum(port_ret) / n
    mean_s = sum(spy_ret) / n
    cov = sum((port_ret[i] - mean_p) * (spy_ret[i] - mean_s) for i in range(n)) / (n - 1)
    var_s = sum((r - mean_s) ** 2 for r in spy_ret) / (n - 1)
    return cov / var_s if var_s > 0 else 1.0


def _compute_jensens_alpha(portfolio_annual_return: float,
                           spy_annual_return: float, beta: float) -> float:
    return portfolio_annual_return - (beta * spy_annual_return)


class AlphaMonitor(MemoryMixin, BaseAgent):
    async def run_once(self):
        port_rows = await self.db.fetch(
            "SELECT total_value, time FROM portfolio_state "
            "WHERE time > now() - INTERVAL '30 days' ORDER BY time ASC"
        )
        spy_rows = await self.db.fetch(
            "SELECT close, time FROM prices WHERE symbol = 'SPY' "
            "AND time > now() - INTERVAL '30 days' ORDER BY time ASC"
        )
        if len(port_rows) < 5 or len(spy_rows) < 5:
            self.logger.info("alpha_monitor_insufficient_data")
            return

        port_vals = [float(r["total_value"]) for r in port_rows]
        spy_vals = [float(r["close"]) for r in spy_rows]
        port_daily = _daily_returns(port_vals)
        sharpe = _compute_sharpe(port_daily)
        beta = _compute_beta(port_vals, spy_vals)

        days = max((datetime.fromisoformat(str(port_rows[-1]["time"])) -
                    datetime.fromisoformat(str(port_rows[0]["time"]))).days, 1)
        port_annual = (port_vals[-1] / port_vals[0]) ** (365 / days) - 1
        spy_annual = (spy_vals[-1] / spy_vals[0]) ** (365 / days) - 1
        jensens_alpha = _compute_jensens_alpha(port_annual, spy_annual, beta)

        await self._classify_and_act(sharpe, jensens_alpha, beta, port_annual, spy_annual)

    async def _classify_and_act(self, sharpe, jensens_alpha, beta, portfolio_annual, spy_annual):
        prev = await self.bus.get("alpha:status") or {}
        prev_tier = prev.get("tier", "learning")

        if sharpe >= 2.0 and jensens_alpha >= 0.05:
            tier = "exceptional_alpha"
        elif sharpe >= 1.5 and jensens_alpha >= 0.02:
            tier = "alpha_achieved"
        else:
            tier = "learning"

        status = {
            "tier": tier,
            "sharpe": round(sharpe, 4),
            "jensens_alpha": round(jensens_alpha * 100, 4),
            "beta": round(beta, 4),
            "portfolio_annual_pct": round(portfolio_annual * 100, 2),
            "spy_annual_pct": round(spy_annual * 100, 2),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await self.bus.set("alpha:status", status)

        if tier != prev_tier:
            self.logger.info("alpha_tier_changed", old=prev_tier, new=tier,
                             sharpe=sharpe, alpha_pct=round(jensens_alpha * 100, 2))
            if tier == "alpha_achieved" and prev_tier == "learning":
                await self.bus.publish("cio.daily_brief", {
                    "subject": "Alpha Achieved - Trading System Update",
                    "report": (
                        f"Alpha achieved.\n\n"
                        f"Sharpe: {sharpe:.2f} (threshold 1.5)\n"
                        f"Jensen's Alpha: {jensens_alpha*100:.2f}% (threshold 2%)\n"
                        f"Beta: {beta:.2f}\n"
                        f"Portfolio annual: {portfolio_annual*100:.2f}%  SPY: {spy_annual*100:.2f}%\n\n"
                        f"Parameters locked. Micro-adjustments only."
                    ),
                })
            elif tier == "exceptional_alpha":
                await self._save_exceptional_strategy(status)
                await self.bus.publish("cio.daily_brief", {
                    "subject": "Exceptional Alpha Achieved - Strategy Locked",
                    "report": (
                        f"Exceptional alpha achieved.\n\n"
                        f"Sharpe: {sharpe:.2f} (threshold 2.0)\n"
                        f"Jensen's Alpha: {jensens_alpha*100:.2f}% (threshold 5%)\n"
                        f"Beta: {beta:.2f}\n"
                        f"All parameters fully locked. Strategy saved to Obsidian vault."
                    ),
                })
            elif tier == "learning" and prev_tier in ("alpha_achieved", "exceptional_alpha"):
                await self.bus.publish("cio.daily_brief", {
                    "subject": "Alpha Eroded - Resuming Optimization",
                    "report": (
                        f"Alpha has eroded below thresholds.\n\n"
                        f"Sharpe: {sharpe:.2f}, Jensen's Alpha: {jensens_alpha*100:.2f}%\n"
                        f"Full optimization resumed."
                    ),
                })

    async def _save_exceptional_strategy(self, status: dict):
        now = datetime.now(timezone.utc)
        body = (
            f"## Exceptional Alpha Strategy\n\n"
            f"**Captured:** {now.isoformat()}\n"
            f"**Sharpe:** {status['sharpe']}\n"
            f"**Jensen's Alpha:** {status['jensens_alpha']}%\n"
            f"**Beta:** {status['beta']}\n\n"
            f"### Parameters\n\nSee current `agent_params.yaml` at this commit.\n"
        )
        await self.write_to_obsidian(
            title=f"Exceptional Alpha {now.strftime('%Y-%m-%d')}",
            body=body,
            tags=["alpha", "strategy", "exceptional"],
        )
