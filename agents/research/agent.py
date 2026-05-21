import json
import re
import httpx
from agents.base import AnalysisAgent

SEC_HEADERS = {"User-Agent": "hedgefund info@hedgefund.local"}
MAX_TEXT_CHARS = 8000

ANALYSIS_PROMPT = """You are a senior equity analyst. Analyze this SEC filing excerpt and return a JSON object with exactly these fields:
{{
  "quality_score": <integer 0-100, earnings quality and consistency>,
  "moat": <"strong" | "moderate" | "weak">,
  "thesis": <one sentence investment thesis>,
  "risks": <one sentence key risks>
}}

Filing ({ticker} {form_type} for period {period}):
{text}

Return ONLY the JSON object, no other text."""


class FundamentalResearchAgent(AnalysisAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._processed: set[str] = set()

    async def run_once(self):
        rows = await self.db.fetch(
            """
            SELECT DISTINCT ON (ticker, form_type) ticker, form_type, period, filing_url, time
            FROM sec_filings
            WHERE form_type IN ('10-K', '10-Q')
            ORDER BY ticker, form_type, time DESC
            """
        )
        for row in rows:
            key = f"{row['ticker']}_{row['form_type']}_{row['period']}"
            if key in self._processed:
                continue
            await self._analyze_filing(row)
            self._processed.add(key)

    async def _fetch_filing_text(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url, headers=SEC_HEADERS)
                if resp.status_code != 200:
                    return None
                text = resp.text
                text = re.sub(r'<[^>]+>', ' ', text)
                text = re.sub(r'\s+', ' ', text).strip()
                return text[:MAX_TEXT_CHARS] if text else None
        except Exception:
            return None

    async def _analyze_filing(self, row: dict):
        ticker = row["ticker"]
        form_type = row["form_type"]
        period = row["period"]
        url = row["filing_url"]

        text = await self._fetch_filing_text(url)
        if not text:
            return

        prompt = ANALYSIS_PROMPT.format(
            ticker=ticker, form_type=form_type, period=period, text=text
        )
        raw = await self.router.chat("research", [{"role": "user", "content": prompt}])

        try:
            analysis = json.loads(raw.strip())
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not match:
                return
            try:
                analysis = json.loads(match.group())
            except json.JSONDecodeError:
                return

        quality = int(analysis.get("quality_score", 50))
        moat = analysis.get("moat", "moderate")
        thesis = analysis.get("thesis", "")
        risks = analysis.get("risks", "")

        signal_type = "fundamental_bullish" if quality >= 70 else ("fundamental_bearish" if quality < 40 else "fundamental_neutral")

        await self.store_signal(
            symbol=ticker,
            signal_type=signal_type,
            confidence=float(quality),
            reasoning=f"{form_type} {period}: {thesis} Risks: {risks}",
            metadata={"quality_score": quality, "moat": moat, "form_type": form_type, "period": period},
        )
        self.logger.info("fundamental_signal", ticker=ticker, quality=quality, moat=moat)
