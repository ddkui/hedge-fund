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
            return float(confirm.json()["level"])
