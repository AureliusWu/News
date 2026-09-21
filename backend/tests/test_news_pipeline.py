from datetime import timedelta
from types import SimpleNamespace

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.db import get_db
from app.main import app
from app.models import Article, Base, Source, SyncState, utcnow
from app.services.miniflux_client import MinifluxError
from app.services.news_normalizer import normalize_entry
from app.services.source_bootstrap import bootstrap_sources, run_cycle, sync_source
from app.services.source_registry import SourceDefinition


def source_fields(slug="publisher", feed_id=1, **overrides):
    return dict(slug=slug, name=slug, publisher=slug, homepage="https://example.org",
        domain="example.org", feed_url="https://example.org/feed/" + slug,
        source_type="official_rss", country="GB", region="world", category="world",
        language="en", miniflux_feed_id=feed_id, enabled=True, **overrides)


def entry(item_id, **overrides):
    return {"id": item_id, "title": "Headline " + str(item_id), "url": "https://example.org/story/" + str(item_id),
        "content": "<p>Excerpt of reporting</p>", "published_at": utcnow().isoformat(), **overrides}


class FakeMiniflux:
    def __init__(self, entries=None, failed_feed=None):
        self.entries = entries or []
        self.failed_feed = failed_feed
        self.feeds = []
        self.categories = []
        self.created = 0

    async def get_feed_entries(self, feed_id, after_entry_id=0, limit=100, **kwargs):
        if feed_id == self.failed_feed:
            raise MinifluxError("feed unavailable")
        selected = [e for e in self.entries if e["id"] > (after_entry_id or 0)]
        selected.sort(key=lambda e: e["id"], reverse=kwargs.get("direction") == "desc")
        return {"entries": selected[:limit], "total": len(selected)}

    async def get_feed(self, feed_id):
        return {"id": feed_id, "parsing_error_count": 0}

    async def list_feeds(self):
        return list(self.feeds)

    async def get_categories(self):
        return list(self.categories)

    async def create_category(self, title):
        self.categories.append({"id": len(self.categories) + 1, "title": title})
        return self.categories[-1]["id"]

    async def create_feed(self, *, feed_url, **kwargs):
        if "broken" in feed_url:
            raise MinifluxError("HTTP 404")
        self.created += 1
        self.feeds.append({"id": self.created, "feed_url": feed_url})
        return self.created

    async def update_feed(self, feed_id, payload):
        for feed in self.feeds:
            if feed["id"] == feed_id:
                feed.update(payload)
                return feed


@pytest_asyncio.fixture
async def db_factory():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


async def test_sync_dedup_and_restart(db_factory):
    client = FakeMiniflux([entry(1), entry(2, url="https://example.org/story/1?utm_source=duplicate"), entry(3)])
    async with db_factory() as db:
        source = Source(**source_fields())
        db.add(source)
        await db.commit()
        assert await sync_source(db, client, source) == 2
    async with db_factory() as db:
        source = await db.get(Source, 1)
        assert await sync_source(db, client, source) == 0
        assert await db.scalar(select(func.count(Article.id))) == 2
        assert (await db.get(SyncState, "feed:1:last_entry_id")).value == "3"


async def test_sync_paginates_and_accepts_late_publication(db_factory, monkeypatch):
    monkeypatch.setattr("app.services.source_bootstrap.settings.news_page_size", 2)
    client = FakeMiniflux([entry(i) for i in range(1, 6)])
    async with db_factory() as db:
        source = Source(**source_fields())
        db.add(source)
        await db.commit()
        assert await sync_source(db, client, source) == 5
        client.entries.append(entry(6, published_at=(utcnow() - timedelta(days=10)).isoformat()))
        assert await sync_source(db, client, source) == 1


async def test_initial_lookback_and_invalid_entry_advance(db_factory):
    client = FakeMiniflux([entry(1, published_at=(utcnow() - timedelta(days=20)).isoformat()),
        entry(2, published_at="1970-01-01T00:00:00Z"), entry(3)])
    async with db_factory() as db:
        source = Source(**source_fields())
        db.add(source)
        await db.commit()
        assert await sync_source(db, client, source) == 1
        assert (await db.get(SyncState, "feed:1:last_entry_id")).value == "3"


async def test_cycle_isolates_failure_and_writes_heartbeat(db_factory):
    async with db_factory() as db:
        db.add_all([Source(**source_fields("bad", 1)), Source(**source_fields("good", 2))])
        await db.commit()
    assert await run_cycle(db_factory, FakeMiniflux([entry(5)], failed_feed=1)) == 1
    async with db_factory() as db:
        assert (await db.get(Source, 1)).health_status == "failed"
        assert (await db.get(Source, 2)).health_status == "ok"
        assert await db.get(SyncState, "worker:last_sync_at") is not None


async def test_disabled_source_is_not_synced(db_factory):
    async with db_factory() as db:
        fields = source_fields()
        fields["enabled"] = False
        source = Source(**fields)
        db.add(source)
        await db.commit()
        assert await sync_source(db, FakeMiniflux([entry(1)]), source) == 0


async def test_bootstrap_idempotence_failure_and_disable(db_factory):
    def definition(slug):
        return SourceDefinition(id=slug, name=slug, publisher=slug, homepage="https://example.org",
            country="GB", region="world", language="en", category="world", feed_url="https://example.org/" + slug)
    client = FakeMiniflux()
    definitions = [definition("broken"), definition("healthy")]
    async with db_factory() as db:
        await bootstrap_sources(db, client, definitions)
        await bootstrap_sources(db, client, definitions)
        assert client.created == 1
        assert await db.scalar(select(func.count(Source.id))) == 2
        definitions[1].enabled = False
        await bootstrap_sources(db, client, definitions)
        assert client.feeds[0]["disabled"] is True


@pytest_asyncio.fixture
async def api(db_factory):
    async with db_factory() as db:
        source = Source(**source_fields())
        db.add(source)
        await db.commit()
        date = utcnow()
        for i in range(1, 66):
            fields = normalize_entry(source, entry(i, title="Climate report " + str(i), published_at=date.isoformat()))
            fields["category"] = "technology" if i % 2 else "world"
            fields["region"] = "japan" if i % 2 else "world"
            fields["language"] = "ja" if i % 2 else "en"
            db.add(Article(**fields))
        await db.commit()
    async def override():
        async with db_factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def test_api_default_pagination_same_timestamp(api):
    first = (await api.get("/api/v1/news")).json()
    assert len(first["items"]) == 30 and first["has_more"]
    second = (await api.get("/api/v1/news", params={"cursor": first["next_cursor"]})).json()
    third = (await api.get("/api/v1/news", params={"cursor": second["next_cursor"]})).json()
    ids = [a["id"] for page in [first, second, third] for a in page["items"]]
    assert ids == list(range(65, 0, -1)) and not third["has_more"]
    assert first["items"][0]["published_at"].endswith("Z")


@pytest.mark.parametrize("param,value,field", [("region","japan","region"),("category","technology","category"),("language","ja","language")])
async def test_api_filters(api, param, value, field):
    response = await api.get("/api/v1/news", params={param: value})
    assert response.status_code == 200
    assert all(a[field] == value for a in response.json()["items"])


async def test_api_source_and_search(api):
    assert len((await api.get("/api/v1/news?source=publisher&q=Climate")).json()["items"]) == 30
    assert (await api.get("/api/v1/news?q=unmatched")).json()["items"] == []
    assert (await api.get("/api/v1/news?q=%20%20")).status_code == 200
    assert (await api.get("/api/v1/news?q=%25")).json()["items"] == []


@pytest.mark.parametrize("cursor", ["", "bad", "%", "W10"])
async def test_api_invalid_cursor_is_400(api, cursor):
    assert (await api.get("/api/v1/news", params={"cursor": cursor})).status_code == 400


@pytest.mark.parametrize("limit", [0, -1, 101])
async def test_api_limit_bounds(api, limit):
    assert (await api.get("/api/v1/news", params={"limit": limit})).status_code == 422


async def test_api_sources_meta_detail_no_internal_fields(api):
    sources = (await api.get("/api/v1/sources")).json()
    assert len(sources) == 1 and sources[0]["health_status"] == "unknown"
    assert not {"feed_url", "miniflux_feed_id", "last_error"} & set(sources[0])
    meta = (await api.get("/api/v1/meta")).json()
    assert meta["source_count"] == 1 and meta["article_count"] == 65
    assert meta["last_sync_at"] is None
    assert (await api.get("/api/v1/news/1")).status_code == 200
    assert (await api.get("/api/v1/news/99999")).status_code == 404