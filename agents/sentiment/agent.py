from agents.base import AnalysisAgent
from agents.sentiment.finbert import FinBertSentiment

SOURCE_WEIGHTS = {
    "reuters": 1.0, "bloomberg": 1.0, "ft": 1.0, "wsj": 0.95,
    "cnbc": 0.8, "marketwatch": 0.75, "seeking alpha": 0.65,
    "wallstreetbets": 0.4, "investing": 0.5, "stocks": 0.45,
}

DEFAULT_TICKER_MAP = {
    "AAPL": ["apple", "aapl"], "MSFT": ["microsoft", "msft"],
    "GOOGL": ["google", "googl", "alphabet"], "AMZN": ["amazon", "amzn"],
    "TSLA": ["tesla", "tsla"], "NVDA": ["nvidia", "nvda"],
    "SPY": ["s&p", "spy", "market"], "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth"], "SOL": ["solana", "sol"],
}


class SentimentAgent(AnalysisAgent):
    def __init__(self, *args, ticker_map: dict | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ticker_map = ticker_map or DEFAULT_TICKER_MAP
        self._finbert = FinBertSentiment()

    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT headline, source, time FROM news_items
            WHERE time > now_or_backtest() - INTERVAL '24 hours'
            ORDER BY time DESC LIMIT 200
            """
        )
        if not rows:
            return

        headlines = [r["headline"] for r in rows]
        results = self._finbert.batch_analyze(headlines)

        for ticker, keywords in self.ticker_map.items():
            relevant = [
                (results[i], rows[i])
                for i, r in enumerate(rows)
                if any(kw in r["headline"].lower() for kw in keywords)
            ]
            if not relevant:
                continue

            total_weight = 0.0
            weighted_compound = 0.0
            for result, row in relevant:
                source = row["source"].lower() if row["source"] else "unknown"
                weight = SOURCE_WEIGHTS.get(source, 0.5)
                weighted_compound += result.compound * weight
                total_weight += weight

            if total_weight == 0:
                continue

            compound = weighted_compound / total_weight
            confidence = min(100.0, abs(compound) * 100 * (1 + len(relevant) / 10))
            label = "bullish" if compound > 0.1 else ("bearish" if compound < -0.1 else "neutral")
            reasoning = (
                f"Analyzed {len(relevant)} articles for {ticker}. "
                f"Weighted compound sentiment: {compound:.3f}. "
                f"Signal: {label}."
            )
            await self.store_signal(
                signal_type=f"sentiment_{label}",
                confidence=confidence,
                reasoning=reasoning,
                symbol=ticker,
                metadata={"compound": round(compound, 4), "article_count": len(relevant), "label": label},
            )
            self.logger.info("sentiment_signal", ticker=ticker, label=label, compound=compound)
