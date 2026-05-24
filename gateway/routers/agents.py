# gateway/routers/agents.py
from fastapi import APIRouter, Depends
from shared.db import Database
from gateway.deps import get_db

router = APIRouter()


@router.get("/health")
async def get_agent_health(db: Database = Depends(get_db)):
    rows = await db.fetch(
        """
        SELECT DISTINCT ON (agent) agent, status, time, message, metadata
        FROM agent_health
        ORDER BY agent, time DESC
        """
    )
    return rows
