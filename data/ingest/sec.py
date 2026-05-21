import httpx
from datetime import datetime, timezone
from data.ingest.base import DataIngestAgent

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SEC_HEADERS = {"User-Agent": "hedgefund info@hedgefund.local"}
FILING_TYPES = {"10-K", "10-Q", "8-K"}


class SecIngestAgent(DataIngestAgent):
    def __init__(self, *args, watchlist: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.watchlist = watchlist
        self._ticker_cik: dict[str, str] = {}

    async def _load_ticker_cik(self, client: httpx.AsyncClient):
        resp = await client.get(SEC_TICKERS_URL, headers=SEC_HEADERS)
        resp.raise_for_status()
        data = resp.json()
        self._ticker_cik = {
            v["ticker"]: str(v["cik_str"]).zfill(10)
            for v in data.values()
        }

    async def run_once(self):
        async with httpx.AsyncClient() as client:
            if not self._ticker_cik:
                await self._load_ticker_cik(client)

            rows = []
            for ticker in self.watchlist:
                cik = self._ticker_cik.get(ticker.upper())
                if not cik:
                    continue
                resp = await client.get(
                    SEC_SUBMISSIONS_URL.format(cik=cik),
                    headers=SEC_HEADERS,
                )
                if resp.status_code != 200:
                    continue
                recent = resp.json().get("filings", {}).get("recent", {})
                forms = recent.get("form", [])
                dates = recent.get("filingDate", [])
                accessions = recent.get("accessionNumber", [])
                periods = recent.get("reportDate", [])

                for form, date, accession, period in zip(forms, dates, accessions, periods):
                    if form not in FILING_TYPES:
                        continue
                    url = (
                        f"https://www.sec.gov/Archives/edgar/data/"
                        f"{int(cik)}/{accession.replace('-', '')}/{accession}-index.htm"
                    )
                    rows.append((
                        datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=timezone.utc),
                        ticker,
                        form,
                        period,
                        url,
                        None,
                    ))

            if rows:
                await self.db.executemany(
                    "INSERT INTO sec_filings (time, ticker, form_type, period, filing_url, summary) "
                    "VALUES ($1, $2, $3, $4, $5, $6) ON CONFLICT DO NOTHING",
                    rows,
                )

        await self.bus.publish("data.sec.updated", {"tickers": self.watchlist})
        self.logger.info("sec_ingested", tickers=len(self.watchlist), filings=len(rows))
