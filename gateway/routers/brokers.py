# gateway/routers/brokers.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from shared.db import Database
from gateway.deps import get_db
from shared import broker_config

router = APIRouter()


class BrokerAccount(BaseModel):
    name: str
    type: str                      # alpaca | ib | capital_com
    enabled: bool = True
    # alpaca
    api_key: str | None = None
    secret_key: str | None = None
    paper: bool | None = None
    # ib
    host: str | None = None
    port: int | None = None
    client_id: int | None = None
    # capital_com
    identifier: str | None = None
    password: str | None = None
    base_url: str | None = None


class ToggleRequest(BaseModel):
    enabled: bool


@router.get("/accounts")
async def list_accounts():
    """List configured broker accounts (secrets masked)."""
    return broker_config.list_brokers()


@router.post("/accounts")
async def add_account(account: BrokerAccount):
    payload = {k: v for k, v in account.model_dump().items() if v is not None}
    try:
        return broker_config.add_broker(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/accounts/{name}")
async def delete_account(name: str):
    if not broker_config.remove_broker(name):
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"removed": name}


@router.patch("/accounts/{name}/toggle")
async def toggle_account(name: str, body: ToggleRequest):
    if not broker_config.toggle_broker(name, body.enabled):
        raise HTTPException(status_code=404, detail="Broker not found")
    return {"name": name, "enabled": body.enabled}


@router.get("/status")
async def broker_status(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (broker_name)
            broker_name, status, fill_price, time
        FROM broker_fills
        ORDER BY broker_name, time DESC
        """
    )
    return [dict(r) for r in rows]


@router.get("/fills")
async def broker_fills(limit: int = 50, db: Database = Depends(get_db)):
    rows = await db.fetch(
        "SELECT * FROM broker_fills ORDER BY time DESC LIMIT $1", limit
    )
    return [dict(r) for r in rows]
