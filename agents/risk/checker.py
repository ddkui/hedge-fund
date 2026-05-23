import numpy as np
import pandas as pd
from typing import Any


class RiskChecker:
    """Async pre-trade risk validation. Imported by PortfolioManagerAgent."""

    def __init__(self, settings: Any):
        self.settings = settings

    async def validate(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        price: float,
        portfolio_value: float,
        peak_value: float,
        open_position_count: int,
        open_symbols: list[str],
        db: Any,
        bus: Any,
    ) -> tuple[bool, str]:
        position_value = quantity * price

        # Position size check
        if portfolio_value > 0 and position_value / portfolio_value > self.settings.risk_max_position_pct:
            return False, f"position_size: {position_value:.0f} exceeds {self.settings.risk_max_position_pct*100:.0f}% of {portfolio_value:.0f}"

        # Open positions count check
        if open_position_count >= self.settings.risk_max_positions:
            return False, f"open_positions: already at max {self.settings.risk_max_positions}"

        # Drawdown check
        if peak_value > 0:
            drawdown = (peak_value - portfolio_value) / peak_value
            if drawdown >= self.settings.risk_max_drawdown_pct:
                return False, f"drawdown: {drawdown*100:.1f}% exceeds max {self.settings.risk_max_drawdown_pct*100:.0f}%"

        # VaR check (cached in Redis for 5 min)
        var_ok, var_msg = await self._check_var(portfolio_value, open_symbols, db, bus)
        if not var_ok:
            return False, var_msg

        # Correlation check
        if open_symbols:
            corr_ok, corr_msg = await self._check_correlation(symbol, open_symbols, db)
            if not corr_ok:
                return False, corr_msg

        return True, ""

    async def _check_var(
        self, portfolio_value: float, open_symbols: list[str], db: Any, bus: Any
    ) -> tuple[bool, str]:
        if not open_symbols:
            return True, ""

        cached = await bus.get("risk:var_cache")
        if cached is not None:
            var_pct = float(cached)
        else:
            rows = await db.fetch(
                """
                SELECT symbol, time, close FROM prices
                WHERE symbol = ANY($1) AND time > NOW() - INTERVAL '30 days'
                ORDER BY symbol, time ASC
                """,
                open_symbols,
            )
            if not rows:
                return True, ""

            df = pd.DataFrame(rows)
            pivot = df.pivot_table(index="time", columns="symbol", values="close", aggfunc="last")
            returns = pivot.pct_change().dropna()
            if returns.empty:
                return True, ""

            portfolio_returns = returns.mean(axis=1)
            var_pct = float(-np.percentile(portfolio_returns, 5))
            await bus.set("risk:var_cache", var_pct, ex=300)

        var_abs = var_pct * portfolio_value
        limit_abs = self.settings.risk_var_limit_pct * portfolio_value
        if var_abs > limit_abs:
            return False, f"var: daily VaR {var_abs:.0f} exceeds limit {limit_abs:.0f}"
        return True, ""

    async def _check_correlation(
        self, symbol: str, open_symbols: list[str], db: Any
    ) -> tuple[bool, str]:
        all_symbols = open_symbols + [symbol]
        rows = await db.fetch(
            """
            SELECT symbol, time, close FROM prices
            WHERE symbol = ANY($1) AND time > NOW() - INTERVAL '20 days'
            ORDER BY symbol, time ASC
            """,
            all_symbols,
        )
        if not rows:
            return True, ""

        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="time", columns="symbol", values="close", aggfunc="last")
        returns = pivot.pct_change().dropna()

        if symbol not in returns.columns:
            return True, ""

        corr_count = 0
        for sym in open_symbols:
            if sym not in returns.columns:
                continue
            pair_corr = returns[symbol].corr(returns[sym])
            if abs(pair_corr) > 0.7:
                corr_count += 1

        if corr_count >= self.settings.risk_max_correlated:
            return False, f"correlation: {symbol} correlated (>0.7) with {corr_count} existing positions (max {self.settings.risk_max_correlated})"
        return True, ""
