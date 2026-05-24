# gateway/deps.py
from shared.db import Database
from shared.bus import RedisBus
from shared.config import settings

_db: Database | None = None
_bus: RedisBus | None = None


def get_db() -> Database:
    assert _db is not None, "Database not initialised"
    return _db


def get_bus() -> RedisBus:
    assert _bus is not None, "RedisBus not initialised"
    return _bus


async def startup():
    global _db, _bus
    _db = Database(settings.db_dsn)
    await _db.connect()
    _bus = RedisBus(settings.redis_url)
    await _bus.connect()


async def shutdown():
    if _db:
        await _db.disconnect()
    if _bus:
        await _bus.disconnect()
