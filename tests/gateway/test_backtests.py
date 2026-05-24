# tests/gateway/test_backtests.py
import pytest


@pytest.mark.asyncio
async def test_get_algos_returns_list(client, mock_db):
    mock_db.fetch.return_value = [
        {"id": 1, "name": "MomentumV1", "quant_agent": "momentum",
         "strategy_type": "momentum", "status": "live",
         "sharpe_ratio": 1.4, "max_drawdown": -0.08, "win_rate": 0.58,
         "trade_count": 42, "created_at": "2026-05-20T00:00:00+00:00",
         "retired_at": None, "retirement_reason": None, "config": None},
    ]
    resp = await client.get("/backtests/algos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "MomentumV1"


@pytest.mark.asyncio
async def test_get_algo_by_id(client, mock_db):
    mock_db.fetchrow.return_value = {
        "id": 1, "name": "MomentumV1", "quant_agent": "momentum",
        "strategy_type": "momentum", "status": "live",
        "sharpe_ratio": 1.4, "max_drawdown": -0.08, "win_rate": 0.58,
        "trade_count": 42, "created_at": "2026-05-20T00:00:00+00:00",
        "retired_at": None, "retirement_reason": None, "config": None,
    }
    resp = await client.get("/backtests/algos/1")
    assert resp.status_code == 200
    assert resp.json()["id"] == 1
