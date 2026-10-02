"""Synthetic native DB + real disk projection tests; no production writes."""

from datetime import timedelta
import json

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.db import get_db
from app.main import app
from app.models import Article, Base, Source, SyncState, utcnow
from app.services.native_events import _file_lock
from app.services.news_normalizer import normalize_entry


@pytest_asyncio.fixture
async def native(tmp_path, monkeypatch):
    root = tmp_path / "events"
    monkeypatch.setattr(settings, "native_event_store_path", str(root))
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    fetched = utcnow() - timedelta(seconds=10)
    completed = utcnow() - timedelta(seconds=2)
    async with factory() as db:
        for i, publisher in enumerate(["Same Publisher", " same publisher ", "Other Publisher"], 1):
            source = Source(slug=f"synthetic-{i}", name=f"Synthetic {i}", publisher=publisher,
                homepage="https://example.org", domain="example.org", feed_url=f"https://example.org/feed/{i}",
                source_type="official_rss", country="GB", region="world", language="en", category="world",
                health_status="ok", enabled=True, miniflux_feed_id=i)
            db.add(source)
            await db.flush()
            fields = normalize_entry(source, {"id": i, "title": "Synthetic council approves river bridge repairs",
                "url": f"https://example.org/story/{i}", "published_at": (completed - timedelta(minutes=i)).isoformat(),
                "content": "<p>Synthetic source material</p>"})
            fields["fetched_at"] = fetched
            db.add(Article(**fields))
        db.add(SyncState(key="worker:last_sync_at", value=completed.isoformat()))
        await db.commit()
    async def override():
        async with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, factory, root, completed
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


async def test_native_generation_evidence_and_no_secret_fields(native):
    client, _, root, completed = native
    response = await client.get("/api/v1/snapshot")
    assert response.status_code == 200
    news = response.json()
    assert news["generated_at"] == completed.isoformat().replace("+00:00", "Z")
    assert news["meta"]["data_origin"] == "native-database" and news["meta"]["formal_release"] is False
    assert len(news["articles"]) == 3
    assert len({s["publisher_id"] for s in news["sources"]}) == 2
    assert all(not {"feed_url", "miniflux_feed_id", "last_error"} & set(source) for source in news["sources"])
    index = (await client.get("/api/v1/events")).json()
    assert len(index["events"]) == 1
    event = index["events"][0]
    assert event["publisher_count"] == 2 and event["article_count"] == 3
    detail = (await client.get("/api/v1/events/" + event["event_id"])).json()
    assert len(detail["articles"]) == 3
    assert [row["published_at"] for row in detail["articles"]] == sorted(row["published_at"] for row in detail["articles"])
    assert news["snapshot_id"] == index["snapshot_id"] == detail["snapshot_id"]
    assert response.headers["cache-control"] == "no-store"
    assert (root / "current.json").exists()


async def test_native_repeated_read_and_new_session_preserve_ids_and_timestamp(native):
    client, _, root, _ = native
    first = (await client.get("/api/v1/snapshot")).json()
    path = root / ("generation." + first["snapshot_id"] + ".json")
    before = path.stat().st_mtime_ns
    second = (await client.get("/api/v1/snapshot")).json()
    assert first == second and path.stat().st_mtime_ns == before


async def test_native_retains_three_immutable_generations(native):
    client, factory, root, completed = native
    publications = []
    for i in range(4):
        async with factory() as db:
            marker = await db.get(SyncState, "worker:last_sync_at")
            marker.value = (completed + timedelta(seconds=i)).isoformat()
            await db.commit()
        response = await client.get("/api/v1/snapshot")
        assert response.status_code == 200
        publications.append(response.json())
    for i, news in enumerate(publications):
        response = await client.get(f"/api/v1/snapshots/{news['snapshot_id']}/{news['events_file']}")
        assert response.status_code == (404 if i == 0 else 200)
        if i:
            assert response.json()["generated_at"] == news["generated_at"]
    assert len(list(root.glob("generation.*.json"))) == 3
    assert len({row["articles"][0]["event_id"] for row in publications}) == 1


@pytest.mark.parametrize("marker", [None, "not-a-date", "2000-01-01T00:00:00Z", "2099-01-01T00:00:00Z", "2026-01-01T00:00:00"])
async def test_native_missing_or_invalid_completed_timestamp_fails_closed(native, marker):
    client, factory, root, _ = native
    async with factory() as db:
        state = await db.get(SyncState, "worker:last_sync_at")
        if marker is None:
            await db.delete(state)
        else:
            state.value = marker
        await db.commit()
    response = await client.get("/api/v1/snapshot")
    assert response.status_code == 503 and response.headers["retry-after"] == "5"
    assert not (root / "current.json").exists()


async def test_native_unconfigured_and_relative_paths_fail_without_fallback(native, monkeypatch):
    client, _, _, _ = native
    for path in (None, "relative-events"):
        monkeypatch.setattr(settings, "native_event_store_path", path)
        assert (await client.get("/api/v1/snapshot")).status_code == 503


async def test_native_missing_pointer_is_not_silently_bootstrapped(native):
    client, _, root, _ = native
    assert (await client.get("/api/v1/snapshot")).status_code == 200
    (root / "current.json").unlink()
    assert (await client.get("/api/v1/snapshot")).status_code == 503
    assert not (root / "current.json").exists()


async def test_native_corrupt_generation_does_not_publish_new_timestamp(native):
    client, _, root, _ = native
    news = (await client.get("/api/v1/snapshot")).json()
    path = root / ("generation." + news["snapshot_id"] + ".json")
    path.write_text("{}", encoding="utf-8")
    assert (await client.get("/api/v1/snapshot")).status_code == 503
    assert path.read_text(encoding="utf-8") == "{}"


async def test_native_digest_mismatch_rejected(native):
    client, _, root, _ = native
    news = (await client.get("/api/v1/snapshot")).json()
    path = root / ("generation." + news["snapshot_id"] + ".json")
    value = json.loads(path.read_text(encoding="utf-8"))
    value["news"]["articles"][0]["title"] = "Synthetic tampering"
    path.write_text(json.dumps(value), encoding="utf-8")
    assert (await client.get("/api/v1/snapshot")).status_code == 503


async def test_native_busy_interprocess_lock_fails_with_retry(native):
    client, _, root, _ = native
    root.mkdir()
    with _file_lock(root):
        response = await client.get("/api/v1/snapshot")
    assert response.status_code == 503 and response.headers["retry-after"] == "5"


async def test_native_disabled_sources_and_partial_fetches_are_excluded(native):
    client, factory, _, completed = native
    async with factory() as db:
        (await db.get(Source, 1)).enabled = False
        (await db.get(Article, 2)).fetched_at = completed + timedelta(seconds=1)
        await db.commit()
    news = (await client.get("/api/v1/snapshot")).json()
    assert len(news["sources"]) == 2 and [row["id"] for row in news["articles"]] == [3]


async def test_native_invalid_ids_paths_and_foreign_generation_are_not_found(native):
    client, _, _, _ = native
    assert (await client.get("/api/v1/events/not-an-id")).status_code == 404
    assert (await client.get("/api/v1/events/e_" + "f" * 24)).status_code == 404
    assert (await client.get("/api/v1/snapshots/" + "f" * 24 + "/events." + "f" * 24 + ".json")).status_code == 404
    news = (await client.get("/api/v1/snapshot")).json()
    assert (await client.get(f"/api/v1/snapshots/{news['snapshot_id']}/private.json")).status_code == 404
    report = await client.get(f"/api/v1/snapshots/{news['snapshot_id']}/{news['source_health_file']}")
    assert report.status_code == 200 and report.json()["health"]["production_acceptance"] is False
async def test_projection_cpu_runs_outside_request_event_loop(native, monkeypatch):
    import threading
    from app.services import native_events as service
    client, _, _, _ = native
    original = service.build_event_index
    caller = threading.get_ident()
    workers = []
    def traced(*args, **kwargs):
        workers.append(threading.get_ident())
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'build_event_index', traced)
    response = await client.get('/api/v1/snapshot')
    assert response.status_code == 200
    assert workers and all(worker != caller for worker in workers)


async def test_completed_worker_change_during_cpu_projection_fails_closed(native, monkeypatch):
    import asyncio
    import threading
    from datetime import timedelta
    from app.models import SyncState
    from app.services import native_events as service
    client, factory, _, completed = native
    original = service.build_event_index
    entered, release = threading.Event(), threading.Event()
    def paused(*args, **kwargs):
        entered.set()
        if not release.wait(5):
            raise RuntimeError('Owned projection-test timeout')
        return original(*args, **kwargs)
    monkeypatch.setattr(service, 'build_event_index', paused)
    request = asyncio.create_task(client.get('/api/v1/snapshot'))
    try:
        assert await asyncio.to_thread(entered.wait, 2)
        async with factory() as db:
            marker = await db.get(SyncState, 'worker:last_sync_at')
            marker.value = (completed + timedelta(seconds=1)).isoformat()
            await db.commit()
        release.set()
        response = await request
        assert response.status_code == 503
        assert 'changed' in response.text.lower()
    finally:
        release.set()
        await request

