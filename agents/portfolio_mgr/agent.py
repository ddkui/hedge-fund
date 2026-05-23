from datetime import datetime, timezone
from agents.base import AnalysisAgent
from shared.config import settings
from agents.risk.checker import RiskChecker


def _direction(signal_type: str) -> str:
    st = signal_type.lower()
    if "bullish" in st:
        return "bullish"
    if "bearish" in st:
        return "bearish"
    return "neutral"


class PortfolioManagerAgent(AnalysisAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def run_once(self):
        checker = RiskChecker(settings=settings)

        agg_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE agent = 'aggregator' AND time > NOW() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """
        )
        quant_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE agent = 'quant_supervisor' AND time > NOW() - INTERVAL '10 minutes'
            ORDER BY time DESC
            """
        )

        quant_by_symbol = {s["symbol"]: s for s in quant_signals}

        state = await self.db.fetchrow(
            "SELECT cash, total_value, peak_value, open_positions FROM portfolio_state ORDER BY time DESC LIMIT 1"
        )
        portfolio_value = float(state["total_value"]) if state else settings.initial_capital
        peak_value = float(state["peak_value"]) if state else settings.initial_capital
        open_count = int(state["open_positions"]) if state else 0

        open_positions = await self.db.fetch(
            "SELECT symbol, direction, quantity FROM positions WHERE status = 'open'"
        )
        open_by_symbol = {p["symbol"]: p for p in open_positions}
        open_symbols = list(open_by_symbol.keys())

        seen_symbols: set[str] = set()
        for sig in agg_signals:
            symbol = sig["symbol"]
            if not symbol or symbol in seen_symbols:
                continue
            seen_symbols.add(symbol)

            agg_conf = float(sig["confidence"])
            agg_dir = _direction(sig["signal_type"])

            quant_sig = quant_by_symbol.get(symbol)
            quant_conf = float(quant_sig["confidence"]) if quant_sig else 0.0

            combined_confidence = agg_conf * 0.60 + quant_conf * 0.40

            # CIO directive check
            directive = await self.bus.get(f"cio:directive:{symbol}")
            if directive:
                action = directive.get("action", "none")
                if action == "low_conviction":
                    combined_confidence *= float(directive.get("confidence_multiplier", 1.0))
                elif action == "avoid_open" and agg_dir != "neutral":
                    if combined_confidence <= 85.0:
                        continue
                    await self._store_cio_override(symbol, "PM overrides avoid_open: confidence > 85", combined_confidence)
                elif action == "request_close":
                    await self._handle_request_close(symbol, open_by_symbol, portfolio_value, peak_value, open_count, open_symbols)
                    continue

            existing = open_by_symbol.get(symbol)

            if agg_dir == "neutral" and existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "consensus_neutral: closing position", combined_confidence)
                continue

            if agg_dir == "neutral":
                continue

            if existing:
                continue  # no pyramiding

            price_rows = await self.db.fetch(
                "SELECT close FROM prices WHERE symbol = $1 ORDER BY time DESC LIMIT 1",
                symbol,
            )
            if not price_rows:
                continue
            current_price = float(price_rows[0]["close"])

            kelly_fraction = (combined_confidence / 100.0) * settings.kelly_multiplier
            position_value = portfolio_value * kelly_fraction
            position_value = max(portfolio_value * 0.005, min(position_value, portfolio_value * settings.risk_max_position_pct))
            quantity = position_value / current_price if current_price > 0 else 0.0

            if quantity <= 0:
                continue

            direction = "long" if agg_dir == "bullish" else "short"

            # Crypto is long-only
            if symbol.upper().endswith("USDT") and direction == "short":
                continue

            ok, reason = await checker.validate(
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                price=current_price,
                portfolio_value=portfolio_value,
                peak_value=peak_value,
                open_position_count=open_count,
                open_symbols=open_symbols,
                db=self.db,
                bus=self.bus,
            )

            if not ok:
                await self._log_risk_event(symbol, "trade_rejected", reason)
                continue

            await self._write_trade(symbol, direction, quantity, current_price, portfolio_value, f"agg_dir={agg_dir}, conf={combined_confidence:.1f}", combined_confidence)

    async def _handle_request_close(self, symbol: str, open_by_symbol: dict, portfolio_value: float, peak_value: float, open_count: int, open_symbols: list):
        fresh_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence FROM signals
            WHERE symbol = $1 AND agent IN ('aggregator', 'quant_supervisor')
              AND time > NOW() - INTERVAL '5 minutes'
            ORDER BY time DESC
            """,
            symbol,
        )
        if not fresh_signals:
            existing = open_by_symbol.get(symbol)
            if existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "CIO request confirmed: no fresh signals", 0.0)
            return

        agg = next((s for s in fresh_signals if s["agent"] == "aggregator"), None)
        quant = next((s for s in fresh_signals if s["agent"] == "quant_supervisor"), None)
        agg_conf = float(agg["confidence"]) if agg else 0.0
        quant_conf = float(quant["confidence"]) if quant else 0.0
        conf = agg_conf * 0.60 + quant_conf * 0.40
        direction = _direction(agg["signal_type"]) if agg else "neutral"

        existing = open_by_symbol.get(symbol)
        if conf > 70 and direction in ("bullish", "bearish"):
            await self._store_cio_override(symbol, f"PM disagrees with request_close: fresh conf={conf:.1f}", conf)
        elif 40 <= conf <= 70:
            await self.store_signal(
                symbol=symbol,
                signal_type="low_conviction",
                confidence=conf * 0.5,
                reasoning="CIO request_close: mixed signals, applying 0.5 multiplier",
            )
        else:
            if existing:
                await self._write_trade(symbol, "close", float(existing["quantity"]), 0.0, portfolio_value, "CIO request confirmed", conf)

    async def _store_cio_override(self, symbol: str, reasoning: str, confidence: float):
        await self.store_signal(
            symbol=symbol,
            signal_type="cio_override",
            confidence=confidence,
            reasoning=reasoning,
            metadata={"cio_override": True},
        )

    async def _write_trade(self, symbol: str, direction: str, quantity: float, price: float, portfolio_value: float, reasoning: str, confidence: float):
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO trades (time, symbol, action, quantity, price, paper, confidence, pm_reasoning)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """,
            now, symbol, direction, quantity, price, settings.paper_trading, confidence, reasoning,
        )
        self.logger.info("trade_written", symbol=symbol, direction=direction, quantity=quantity)

    async def _log_risk_event(self, symbol: str, action_taken: str, reason: str):
        now = datetime.now(timezone.utc)
        limit_type = reason.split(":")[0].strip() if ":" in reason else "unknown"
        await self.db.execute(
            "INSERT INTO risk_events (time, agent, symbol, limit_type, details, action_taken) VALUES ($1,$2,$3,$4,$5,$6)",
            now, self.name, symbol, limit_type, reason, action_taken,
        )
