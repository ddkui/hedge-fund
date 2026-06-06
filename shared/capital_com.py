# shared/capital_com.py
"""
Capital.com broker adapter.

CapitalComSession  — REST session (auth, token refresh, order placement)
CapitalPriceFeed   — Polls /api/v1/markets/{epic} and upserts to prices table
"""
import asyncio
from datetime import datetime, timezone
from typing import Any
import httpx
import structlog
from shared.config import settings


class CapitalComSession:
    """
    Manages a Capital.com REST session.

    Auth: POST /api/v1/session → CST + X-SECURITY-TOKEN headers.
    Tokens expire after 10 min; _refresh_loop re-auths every 9 min.
    place_order: POST /api/v1/positions → GET /api/v1/confirms/{ref} → fill price.
    """

    def __init__(self, base_url: str, api_key: str, identifier: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.identifier = identifier
        self.password = password
        self.cst: str = ""
        self.security_token: str = ""
        self.logger = structlog.get_logger()
        self._refresh_task: asyncio.Task | None = None

    def _auth_headers(self) -> dict[str, str]:
        return {
            "X-CAP-API-KEY": self.api_key,
            "CST": self.cst,
            "X-SECURITY-TOKEN": self.security_token,
            "Content-Type": "application/json",
        }

    async def _authenticate(self) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/session",
                headers={"X-CAP-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"identifier": self.identifier, "password": self.password, "encryptedPassword": False},
            )
            resp.raise_for_status()
            cst = resp.headers.get("CST")
            sec = resp.headers.get("X-SECURITY-TOKEN")
            if not cst or not sec:
                raise ValueError(f"Capital.com auth response missing tokens (CST={cst!r}, X-SECURITY-TOKEN={sec!r})")
            self.cst = cst
            self.security_token = sec
            self.logger.info("capital_com_authenticated")

    async def connect(self) -> None:
        """Authenticate and start the background token-refresh loop."""
        await self._authenticate()
        self._refresh_task = asyncio.create_task(self._refresh_loop())

    async def disconnect(self) -> None:
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

    async def _refresh_loop(self) -> None:
        """Re-authenticate every 9 minutes to keep tokens alive."""
        while True:
            await asyncio.sleep(540)  # 9 minutes
            try:
                await self._authenticate()
            except Exception as exc:
                self.logger.error("capital_com_refresh_failed", error=str(exc))

    async def place_order(self, epic: str, direction: str, size: float) -> float | None:
        """
        Place a market CFD order on Capital.com.

        direction: "BUY" or "SELL"
        Returns the fill price (level), or None on unrecoverable failure.
        """
        try:
            return await self._try_place_order(epic, direction, size)
        except Exception as exc:
            self.logger.error("capital_com_order_failed_first_attempt", epic=epic, error=str(exc))
            await asyncio.sleep(2)
            try:
                return await self._try_place_order(epic, direction, size)
            except Exception as exc2:
                self.logger.error("capital_com_order_failed_final", epic=epic, error=str(exc2))
                return None

    async def _try_place_order(self, epic: str, direction: str, size: float) -> float:
        async with httpx.AsyncClient(timeout=10) as client:
            # Place position
            resp = await client.post(
                f"{self.base_url}/api/v1/positions",
                headers=self._auth_headers(),
                json={
                    "epic": epic,
                    "direction": direction,
                    "size": size,
                    "guaranteedStop": False,
                    "trailingStop": False,
                },
            )
            if resp.status_code == 401:
                self.logger.warning("capital_com_401_reauthing")
                await self._authenticate()
                # Retry once after re-auth
                resp = await client.post(
                    f"{self.base_url}/api/v1/positions",
                    headers=self._auth_headers(),
                    json={
                        "epic": epic,
                        "direction": direction,
                        "size": size,
                        "guaranteedStop": False,
                        "trailingStop": False,
                    },
                )
            resp.raise_for_status()
            deal_ref = resp.json()["dealReference"]

            # Confirm to get fill price
            confirm = await client.get(
                f"{self.base_url}/api/v1/confirms/{deal_ref}",
                headers=self._auth_headers(),
            )
            confirm.raise_for_status()
            confirm_data = confirm.json()
            deal_status = confirm_data.get("dealStatus", "ACCEPTED")
            if deal_status != "ACCEPTED":
                raise ValueError(f"Capital.com order rejected: {deal_status} — {confirm_data.get('rejectReason', 'unknown')}")
            return float(confirm_data["level"])


def get_leverage(asset_class: str) -> int:
    """Return leverage multiplier for a given asset class."""
    mapping = {
        "forex": settings.capital_com_leverage_forex,
        "indices": settings.capital_com_leverage_indices,
        "commodities": settings.capital_com_leverage_commodities,
        "shares": settings.capital_com_leverage_shares,
    }
    return mapping.get(asset_class.lower(), 1)


class CapitalPriceFeed:
    """
    Polls Capital.com /api/v1/markets/{epic} for each epic in the watchlist
    and upserts the mid-price into the prices table.

    On error: exponential backoff (1s → 2s → 4s … cap 60s), reset on success.
    """

    def __init__(self, session: CapitalComSession, db: Any, epics: list[str], interval_seconds: int = 5):
        self.session = session
        self.db = db
        self.epics = epics
        self.interval_seconds = interval_seconds
        self.logger = structlog.get_logger()

    async def run(self) -> None:
        backoff = 1
        while True:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    for epic in self.epics:
                        try:
                            await self._tick(epic, client)
                        except Exception as epic_exc:
                            self.logger.error("capital_feed_tick_error", epic=epic, error=str(epic_exc))
                backoff = 1  # reset on success
                await asyncio.sleep(self.interval_seconds)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.error("capital_feed_error", error=str(exc))
                await asyncio.sleep(min(backoff, 60))
                backoff = min(backoff * 2, 60)

    async def _tick(self, epic: str, client: httpx.AsyncClient) -> None:
        resp = await client.get(
            f"{self.session.base_url}/api/v1/markets/{epic}",
            headers=self.session._auth_headers(),
        )
        if resp.status_code == 401:
            self.logger.warning("capital_feed_401_reauthing", epic=epic)
            await self.session._authenticate()
            resp = await client.get(
                f"{self.session.base_url}/api/v1/markets/{epic}",
                headers=self.session._auth_headers(),
            )
        resp.raise_for_status()
        snap = resp.json()["snapshot"]
        bid = float(snap["bid"])
        ask = float(snap["offer"])
        mid = (bid + ask) / 2.0
        now = datetime.now(timezone.utc)
        await self.db.execute(
            """
            INSERT INTO prices (time, symbol, asset_class, open, high, low, close, volume)
            VALUES ($1, $2, 'cfd', $3, $3, $3, $3, 0)
            ON CONFLICT ON CONSTRAINT prices_time_symbol_unique DO UPDATE SET close = EXCLUDED.close
            """,
            now, epic, mid,
        )
        self.logger.debug("capital_feed_tick", epic=epic, mid=mid)
