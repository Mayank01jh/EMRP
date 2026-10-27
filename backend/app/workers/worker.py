"""Arq worker settings and entrypoint."""
from __future__ import annotations

from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.database import connect_db, close_db
from app.core.redis_client import connect_redis, close_redis
from app.core.logging import configure_logging
from app.workers.tasks import outbox_relay, offer_sweeper, process_dispatch


async def startup(ctx: dict) -> None:
    configure_logging()
    await connect_db()
    await connect_redis()


async def shutdown(ctx: dict) -> None:
    await close_db()
    await close_redis()


class WorkerSettings:
    functions = [process_dispatch, outbox_relay, offer_sweeper]
    cron_jobs = [
        # Outbox relay every 2 seconds
        {"name": "outbox_relay", "coroutine": outbox_relay, "second": {0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44, 46, 48, 50, 52, 54, 56, 58}},
        # Offer sweeper every 5 seconds
        {"name": "offer_sweeper", "coroutine": offer_sweeper, "second": {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55}},
    ]
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 50
    job_timeout = 30
    retry_jobs = True
    max_tries = 3

    @property
    def redis_settings(self) -> RedisSettings:
        settings = get_settings()
        return RedisSettings.from_dsn(settings.redis_url)
