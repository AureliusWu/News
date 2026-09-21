import logging
import time
from datetime import timedelta

from sqlalchemy import or_, select

from app.core.config import settings
from app.models import Article, Source, SyncState, utcnow
from app.services.miniflux_client import MinifluxError
from app.services.news_normalizer import normalize_entry, parse_datetime
from app.services.source_registry import load_sources, source_domain

LOGGER = logging.getLogger("news.worker")


async def set_state(db, key, value):
    state = await db.get(SyncState, key)
    if state is None:
        db.add(SyncState(key=key, value=str(value)))
    else:
        state.value = str(value)
        state.updated_at = utcnow()


async def bootstrap_sources(db, client, definitions=None):
    definitions = definitions if definitions is not None else load_sources(settings.source_registry_path)
    feeds = await client.list_feeds()
    categories = {c["title"]: c["id"] for c in await client.get_categories()}
    existing = {s.slug: s for s in (await db.scalars(select(Source))).all()}
    configured = {s.id for s in definitions}
    for old in existing.values():
        if old.slug not in configured:
            old.enabled = False
            old.health_status = "disabled"
            if old.miniflux_feed_id:
                try:
                    await client.update_feed(old.miniflux_feed_id, {"disabled": True})
                except MinifluxError:
                    LOGGER.warning("event=disable_failed source=%s", old.slug)
    await db.commit()
    for definition in sorted(definitions, key=lambda s: s.priority):
        start = time.monotonic()
        source = existing.get(definition.id)
        if source is None:
            source = Source(slug=definition.id)
            db.add(source)
            existing[source.slug] = source
        for field in ("name", "publisher", "homepage", "country", "region", "language", "category", "priority", "notes", "enabled", "source_type", "rsshub_path"):
            setattr(source, field, getattr(definition, field))
        source.domain = source_domain(definition.homepage)
        source.feed_url = definition.feed_url if definition.source_type == "official_rss" else settings.rsshub_url.rstrip("/") + definition.rsshub_path
        source.health_status = "unknown" if definition.enabled else "disabled"
        await db.commit()
        try:
            match = next((f for f in feeds if f["id"] == source.miniflux_feed_id or f["feed_url"] == source.feed_url), None)
            if not definition.enabled:
                if match:
                    await client.update_feed(match["id"], {"disabled": True})
                continue
            category_title = "Global News / " + definition.category
            if category_title not in categories:
                categories[category_title] = await client.create_category(category_title)
            category_id = categories[category_title]
            if match:
                source.miniflux_feed_id = match["id"]
                await client.update_feed(match["id"], dict(feed_url=source.feed_url, category_id=category_id,
                    disabled=False, crawler=definition.crawler, user_agent=definition.user_agent or ""))
            else:
                try:
                    source.miniflux_feed_id = await client.create_feed(feed_url=source.feed_url, category_id=category_id,
                        crawler=definition.crawler, user_agent=definition.user_agent)
                except MinifluxError:
                    feeds = await client.list_feeds()
                    match = next((f for f in feeds if f["feed_url"] == source.feed_url), None)
                    if not match:
                        raise
                    source.miniflux_feed_id = match["id"]
                feeds.append({"id": source.miniflux_feed_id, "feed_url": source.feed_url})
            source.last_error = None
        except MinifluxError as exc:
            source.health_status = "failed"
            source.last_error = str(exc)
        source.last_checked_at = utcnow()
        await db.commit()
        LOGGER.info("event=bootstrap source=%s feed_id=%s health=%s duration=%.2f", source.slug, source.miniflux_feed_id, source.health_status, time.monotonic() - start)
    return list(existing.values())


async def sync_source(db, client, source):
    if not source.enabled or not source.miniflux_feed_id:
        return 0
    key = f"feed:{source.miniflux_feed_id}:last_entry_id"
    state = await db.get(SyncState, key)
    watermark = int(state.value) if state and state.value else 0
    cutoff = utcnow() - timedelta(days=settings.news_initial_lookback_days) if not state else None
    inserted = 0
    while True:
        payload = await client.get_feed_entries(source.miniflux_feed_id, after_entry_id=watermark, limit=settings.news_page_size)
        entries = payload["entries"]
        if not entries:
            await set_state(db, key, watermark)
            await db.commit()
            break
        next_watermark = watermark
        for entry in entries:
            next_watermark = max(next_watermark, entry["id"])
            try:
                fields = normalize_entry(source, entry)
            except (ValueError, TypeError, KeyError):
                LOGGER.warning("event=invalid_entry source=%s feed_id=%s entry_id=%s", source.slug, source.miniflux_feed_id, entry["id"])
                continue
            if cutoff and fields["published_at"] < cutoff:
                continue
            existing = await db.scalar(select(Article).where(or_(Article.miniflux_entry_id == fields["miniflux_entry_id"], Article.canonical_hash == fields["canonical_hash"])))
            if existing is None:
                db.add(Article(**fields))
                inserted += 1
            elif existing.miniflux_entry_id == fields["miniflux_entry_id"]:
                for field in ("title", "summary", "image_url", "author", "content_html"):
                    setattr(existing, field, fields[field])
        if next_watermark <= watermark:
            raise MinifluxError("entries: non-advancing cursor")
        watermark = next_watermark
        await set_state(db, key, watermark)
        # The watermark and its articles commit together. Failed pages replay on retry.
        await db.commit()
        if len(entries) < settings.news_page_size:
            break
    return inserted


async def check_source_health(db, client, source):
    source.last_checked_at = utcnow()
    if not source.enabled:
        source.health_status = "disabled"
    elif not source.miniflux_feed_id:
        source.health_status = "failed"
    else:
        feed = await client.get_feed(source.miniflux_feed_id)
        latest = await client.get_feed_entries(source.miniflux_feed_id, limit=1, order="published_at", direction="desc")
        entries = latest["entries"]
        if feed.get("parsing_error_count", 0):
            source.health_status = "failed"
            source.last_error = f"Miniflux parsing errors: {feed['parsing_error_count']}"
        elif not entries:
            source.health_status = "warning"
            source.last_error = "Feed has no entries"
        else:
            try:
                published = parse_datetime(entries[0].get("published_at"))
                recent = published >= utcnow() - timedelta(days=7)
            except ValueError:
                recent = False
            source.health_status = "ok" if recent else "warning"
            source.last_error = None if recent else "No valid entry in the last 7 days"
            if recent:
                source.last_success_at = utcnow()
    await db.commit()


async def run_cycle(session_factory, client):
    async with session_factory() as db:
        source_ids = list((await db.scalars(select(Source.id).where(Source.enabled.is_(True)).order_by(Source.priority))).all())
    inserted = 0
    for source_id in source_ids:
        async with session_factory() as db:
            source = await db.get(Source, source_id)
            slug, feed_id = source.slug, source.miniflux_feed_id
            started = time.monotonic()
            try:
                count = await sync_source(db, client, source)
                inserted += count
                await check_source_health(db, client, source)
                LOGGER.info("event=sync source=%s feed_id=%s count=%s duration=%.2f", slug, feed_id, count, time.monotonic() - started)
            except Exception as exc:
                await db.rollback()
                source = await db.get(Source, source_id)
                source.health_status = "failed"
                source.last_error = str(exc) if isinstance(exc, MinifluxError) else type(exc).__name__
                source.last_checked_at = utcnow()
                await db.commit()
                LOGGER.warning("event=sync_failed source=%s feed_id=%s error=%s", slug, feed_id, source.last_error)
    async with session_factory() as db:
        await set_state(db, "worker:last_sync_at", utcnow().isoformat())
        await db.commit()
    return inserted