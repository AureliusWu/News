"""Miniflux fetches feeds; this process synchronizes its API into our DB."""
import argparse
import asyncio
import logging
import signal
import time
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.services.miniflux_client import MinifluxClient
from app.services.source_bootstrap import bootstrap_sources, run_cycle

LOGGER = logging.getLogger("news.worker")


async def heartbeat(stop):
    while not stop.is_set():
        Path("/tmp/news-worker-heartbeat").touch()
        try:
            await asyncio.wait_for(stop.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass


async def main(once=False):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)
    pulse = asyncio.create_task(heartbeat(stop))
    client = MinifluxClient()
    try:
        async with engine.connect() as lock:
            if not await lock.scalar(text("SELECT pg_try_advisory_lock(2026002)")):
                raise RuntimeError("Another news worker holds the database lock")
            bootstrapped_at = 0.0
            while not stop.is_set():
                try:
                    await client.healthcheck()
                    if not bootstrapped_at or time.monotonic() - bootstrapped_at > 900:
                        async with SessionLocal() as db:
                            await bootstrap_sources(db, client)
                        if not bootstrapped_at and settings.news_initial_full_refresh:
                            await client.refresh_all_feeds()
                        bootstrapped_at = time.monotonic()
                    count = await run_cycle(SessionLocal, client)
                    LOGGER.info("event=cycle_complete count=%s", count)
                    if once:
                        break
                except Exception as exc:
                    LOGGER.error("event=cycle_failed error=%s", type(exc).__name__)
                    if once:
                        raise
                try:
                    await asyncio.wait_for(stop.wait(), timeout=settings.news_sync_interval_seconds)
                except asyncio.TimeoutError:
                    pass
    finally:
        stop.set()
        await pulse
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    asyncio.run(main(parser.parse_args().once))
