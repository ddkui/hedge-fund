import json
import re
from datetime import datetime, timezone
from agents.base import AnalysisAgent
from shared.config import settings
from shared.memory import MemoryMixin

DIRECTIVE_TTL_SECONDS = 25 * 3600  # 25 hours


class CIOAgent(MemoryMixin, AnalysisAgent):
    async def run_once(self):
        all_signals = await self.db.fetch(
            """
            SELECT agent, symbol, signal_type, confidence, reasoning, time
            FROM signals
            WHERE time > now_or_backtest() - INTERVAL '24 hours'
            ORDER BY time DESC
            LIMIT 200
            """
        )
        open_positions = await self.db.fetch(
            "SELECT symbol, direction, quantity, entry_price FROM positions WHERE status = 'open'"
        )
        price_rows = await self.db.fetch(
            "SELECT DISTINCT ON (symbol) symbol, close FROM prices WHERE symbol = ANY($1) ORDER BY symbol, time DESC",
            [p["symbol"] for p in open_positions] or ["__none__"],
        )
        prices = {r["symbol"]: float(r["close"]) for r in price_rows}

        positions_with_pnl = []
        for pos in open_positions:
            price = prices.get(pos["symbol"], float(pos["entry_price"]))
            direction_multiplier = -1.0 if pos["direction"] == "short" else 1.0
            pnl = (price - float(pos["entry_price"])) * float(pos["quantity"]) * direction_multiplier
            positions_with_pnl.append({
                "symbol": pos["symbol"],
                "direction": pos["direction"],
                "quantity": float(pos["quantity"]),
                "entry_price": float(pos["entry_price"]),
                "current_price": price,
                "unrealized_pnl": round(pnl, 2),
            })

        closed_trades = await self.db.fetch(
            """
            SELECT symbol, action, quantity, price, pm_reasoning, time
            FROM trades
            WHERE status = 'executed' AND time > now_or_backtest() - INTERVAL '7 days'
            ORDER BY time DESC
            LIMIT 50
            """
        )
        macro_signal = await self.db.fetch(
            "SELECT signal_type, confidence, time FROM signals WHERE agent = 'macro' ORDER BY time DESC LIMIT 1"
        )
        risk_events = await self.db.fetch(
            "SELECT limit_type, details, action_taken, time FROM risk_events WHERE time > now_or_backtest() - INTERVAL '24 hours'"
        )
        cio_overrides = await self.db.fetch(
            "SELECT symbol, reasoning, time FROM signals WHERE signal_type = 'cio_override' AND time > now_or_backtest() - INTERVAL '24 hours'"
        )

        # --- Kronos research forecasts (latest per symbol, last 8 hours) ---
        kronos_rows = await self.db.fetch(
            """
            SELECT DISTINCT ON (symbol)
                symbol, pred_change_pct, signal_type, confidence, pred_close, pred_high, pred_low, time
            FROM kronos_forecasts
            WHERE time > now_or_backtest() - INTERVAL '8 hours'
            ORDER BY symbol, time DESC
            """
        )
        kronos_forecasts = [dict(r) for r in kronos_rows]

        macro_regime = macro_signal[0]["signal_type"] if macro_signal else "unknown"

        prompt = self._build_prompt(
            positions=positions_with_pnl,
            closed_trades=[dict(r) for r in closed_trades],
            macro_regime=macro_regime,
            risk_events=[dict(r) for r in risk_events],
            cio_overrides=[dict(r) for r in cio_overrides],
            recent_signals=[dict(r) for r in all_signals[:30]],
            kronos_forecasts=kronos_forecasts,
        )

        raw_response = await self.router.chat(
            "cio",
            [
                {"role": "system", "content": "You are a Chief Investment Officer. Respond only with a valid JSON array of directives."},
                {"role": "user", "content": prompt},
            ],
        )

        directives = self._parse_directives(raw_response)

        for directive in directives:
            if directive.get("action", "none") == "none":
                continue
            symbol = directive.get("symbol")
            if not symbol:
                continue
            await self.bus.set(
                f"cio:directive:{symbol}",
                {
                    "action": directive["action"],
                    "reason": directive.get("reason", ""),
                    "confidence_multiplier": float(directive.get("confidence_multiplier", 1.0)),
                },
                ex=DIRECTIVE_TTL_SECONDS,
            )
            self.logger.info("cio_directive_set", symbol=symbol, action=directive["action"])

        pm_pushback_note = ""
        if cio_overrides:
            pm_pushback_note = f" PM overrode {len(cio_overrides)} CIO directive(s)."

        # Build the full daily report (what gets emailed)
        now = datetime.now(timezone.utc)
        full_report = self._build_daily_report(
            now=now,
            macro_regime=macro_regime,
            positions=positions_with_pnl,
            risk_events=[dict(r) for r in risk_events],
            directives=directives,
            cio_overrides_count=len(cio_overrides),
            kronos_forecasts=kronos_forecasts,
        )

        brief_reasoning = (
            f"Regime={macro_regime}. {len(directives)} directives issued.{pm_pushback_note} "
            f"Kronos coverage: {len(kronos_forecasts)} symbols. "
            f"\n\n{full_report}"
        )

        await self.store_signal(
            signal_type="daily_brief",
            confidence=100.0,
            reasoning=brief_reasoning,
            metadata={
                "positions": positions_with_pnl,
                "directives": directives,
                "regime": macro_regime,
                "risk_events_count": len(risk_events),
                "cio_overrides_count": len(cio_overrides),
                "kronos_symbol_count": len(kronos_forecasts),
            },
        )

        # Publish to Redis → triggers Gmail notification via NotificationService
        await self.bus.publish("cio.daily_brief", {
            "subject": f"AI Hedge Fund Daily Brief — {now.strftime('%Y-%m-%d')}",
            "report": full_report,
            "regime": macro_regime,
            "directives_count": len(directives),
            "kronos_symbols": len(kronos_forecasts),
        })

        await self.write_to_obsidian(
            title=f"CIO Brief {now.strftime('%Y-%m-%d')}",
            body=full_report,
            tags=["cio", "brief"],
        )

    # ------------------------------------------------------------------ #
    #  LLM prompt                                                           #
    # ------------------------------------------------------------------ #

    def _build_prompt(
        self, positions, closed_trades, macro_regime,
        risk_events, cio_overrides, recent_signals, kronos_forecasts,
    ) -> str:
        kronos_section = ""
        if kronos_forecasts:
            lines = []
            for kf in kronos_forecasts:
                arrow = "▲" if "bullish" in kf["signal_type"] else ("▼" if "bearish" in kf["signal_type"] else "→")
                lines.append(
                    f"  {arrow} {kf['symbol']}: {kf['pred_change_pct']:+.2f}%  conf={kf['confidence']:.0f}%"
                )
            kronos_section = "\n\nKronos AI model price forecasts (24-candle horizon):\n" + "\n".join(lines)

        return f"""You are reviewing the hedge fund portfolio. Current macro regime: {macro_regime}.

Open positions with unrealized P&L:
{json.dumps(positions, indent=2)}

Recent closed trades (last 7 days):
{json.dumps(closed_trades[:10], indent=2, default=str)}

Recent risk events (last 24h):
{json.dumps(risk_events, indent=2, default=str)}

PM pushbacks on prior CIO directives:
{json.dumps(cio_overrides, indent=2, default=str)}
{kronos_section}

Based on all of the above, provide a JSON array of per-symbol directives. Each item:
{{
  "symbol": "TICKER",
  "action": "low_conviction" | "avoid_open" | "request_close" | "none",
  "confidence_multiplier": 0.0-1.0,
  "reason": "one sentence"
}}

Return ONLY the JSON array, nothing else."""

    # ------------------------------------------------------------------ #
    #  Daily email report                                                   #
    # ------------------------------------------------------------------ #

    def _build_daily_report(
        self, now, macro_regime, positions, risk_events,
        directives, cio_overrides_count, kronos_forecasts,
    ) -> str:
        date_str = now.strftime("%Y-%m-%d %H:%M UTC")

        # Portfolio section
        if positions:
            pos_lines = [
                f"  • {p['symbol']} {p['direction'].upper()} "
                f"qty={p['quantity']:.4f} entry={p['entry_price']:.4f} "
                f"now={p['current_price']:.4f} pnl={p['unrealized_pnl']:+.2f}"
                for p in positions
            ]
        else:
            pos_lines = ["  No open positions."]

        # Risk section
        if risk_events:
            risk_lines = [f"  ⚠️  {e['limit_type']}: {e['details']} → {e['action_taken']}" for e in risk_events]
        else:
            risk_lines = ["  No risk events in last 24h."]

        # Directives section
        if directives:
            dir_lines = [
                f"  • {d.get('symbol','?')}: {d.get('action','none')} "
                f"(×{d.get('confidence_multiplier',1.0):.1f}) — {d.get('reason','')}"
                for d in directives if d.get("action", "none") != "none"
            ]
            if not dir_lines:
                dir_lines = ["  No active directives."]
        else:
            dir_lines = ["  No directives issued."]

        # Kronos section
        if kronos_forecasts:
            bullish = [kf for kf in kronos_forecasts if "bullish" in kf["signal_type"]]
            bearish = [kf for kf in kronos_forecasts if "bearish" in kf["signal_type"]]
            neutral = [kf for kf in kronos_forecasts if "neutral" in kf["signal_type"]]

            def kf_line(kf):
                arrow = "▲" if "bullish" in kf["signal_type"] else ("▼" if "bearish" in kf["signal_type"] else "→")
                direction = kf["signal_type"].replace("_signal", "").upper()
                return (
                    f"  {arrow} {kf['symbol']:<12} {direction:<8} "
                    f"{kf['pred_change_pct']:>+7.2f}%  "
                    f"now={kf.get('pred_close',0):.4f}  conf={kf['confidence']:.0f}%"
                )

            kronos_lines = (
                (["  🟢 BULLISH:"] + [kf_line(k) for k in bullish] if bullish else []) +
                (["  🔴 BEARISH:"] + [kf_line(k) for k in bearish] if bearish else []) +
                (["  ⬜ NEUTRAL:"] + [kf_line(k) for k in neutral] if neutral else [])
            )
            kronos_summary = f"  {len(bullish)} bullish · {len(bearish)} bearish · {len(neutral)} neutral across {len(kronos_forecasts)} symbols"
        else:
            kronos_lines = ["  No Kronos forecasts available (agent may still be loading model)."]
            kronos_summary = ""

        sections = [
            "=" * 60,
            f"  AI HEDGE FUND — DAILY BRIEF",
            f"  {date_str}",
            "=" * 60,
            "",
            f"MACRO REGIME:  {macro_regime.upper().replace('_', ' ')}",
            "",
            "─" * 60,
            "OPEN POSITIONS",
            "─" * 60,
        ] + pos_lines + [
            "",
            "─" * 60,
            "RISK EVENTS (last 24h)",
            "─" * 60,
        ] + risk_lines + [
            "",
            "─" * 60,
            "CIO DIRECTIVES",
            "─" * 60,
        ] + dir_lines + [
            f"  PM overrides today: {cio_overrides_count}",
            "",
            "─" * 60,
            f"KRONOS AI PRICE FORECASTS  (24-candle horizon)",
            "─" * 60,
        ] + ([kronos_summary] if kronos_summary else []) + kronos_lines + [
            "",
            "=" * 60,
            "  Generated by AI Hedge Fund System",
            "=" * 60,
        ]

        return "\n".join(sections)

    # ------------------------------------------------------------------ #
    #  Parsing                                                              #
    # ------------------------------------------------------------------ #

    def _parse_directives(self, raw: str) -> list[dict]:
        try:
            cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
            result = json.loads(cleaned)
            if not isinstance(result, list):
                raise ValueError("Expected JSON array")
            return result
        except (json.JSONDecodeError, ValueError):
            self.logger.warning("cio_parse_failed", raw=raw[:200])
            return []
