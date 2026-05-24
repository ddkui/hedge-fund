# agents/ops/notifications.py
"""Run as subprocess: python agents/ops/notifications.py"""
import asyncio
import sys
sys.path.insert(0, ".")
from shared.bus import RedisBus
from shared.config import settings
from shared.notifications import NotificationService


async def main():
    if not settings.gmail_sender or not settings.gmail_app_password:
        print("Gmail not configured (GMAIL_SENDER / GMAIL_APP_PASSWORD missing) — notifications disabled")
        return
    bus = RedisBus(settings.redis_url)
    await bus.connect()
    svc = NotificationService(
        sender=settings.gmail_sender,
        recipient=settings.gmail_sender,
        app_password=settings.gmail_app_password,
    )
    print("Notification service running...")
    try:
        await svc.run(bus)
    finally:
        await bus.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
