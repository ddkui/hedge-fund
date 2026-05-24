# tests/gateway/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
import gateway.deps as deps_module


@pytest.fixture
async def mock_db():
    db = AsyncMock()
    db.fetch = AsyncMock(return_value=[])
    db.fetchrow = AsyncMock(return_value=None)
    db.execute = AsyncMock()
    return db


@pytest.fixture
async def mock_bus():
    bus = AsyncMock()
    bus.get = AsyncMock(return_value=None)
    bus.publish = AsyncMock()
    return bus


@pytest.fixture
async def client(mock_db, mock_bus):
    deps_module._db = mock_db
    deps_module._bus = mock_bus
    from gateway.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
