"""Optional, bounded event projection of the native database, not a Pages fallback.

The database remains authoritative. A configured persistent directory stores the
stable-ID registry and three immutable generations without a schema migration.
The completed worker timestamp is never replaced with the time of a request.
"""

import asyncio
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.core.config import settings
from app.models import Article, Source, SyncState
from app.schemas import ArticleResponse, SourceResponse
from app.services.event_index import build_event_index, validate_registry

GENERATION = re.compile(r"^[a-f0-9]{24}$")
EVENT = re.compile(r"^e_[a-f0-9]{24}$")
MAX_ARTICLES = 2000
MAX_BUNDLE = 16 * 1024 * 1024
MAX_POINTER = 4096
_lock = asyncio.Lock()


class NativeEventsUnavailable(Exception):
    """An explicit, fail-closed operational gate, with no secret-bearing cause."""


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp has no timezone")
    return parsed.astimezone(timezone.utc)


def _encoded(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _digest(news: dict) -> str:
    return hashlib.sha256(_encoded({"articles": news["articles"], "sources": news["sources"]})).hexdigest()


def _generation(news: dict) -> str:
    version = ":" + news["meta"]["version"] if news.get("generation_method") == "native-version-bound-v1" else ""
    return hashlib.sha256((news["generated_at"] + ":" + news["content_sha256"] + version).encode("utf-8")).hexdigest()[:24]


def _read(path: Path, limit: int):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("event store exceeds its bound")
    return json.loads(raw)


def _atomic(path: Path, value, limit: int):
    raw = _encoded(value)
    if len(raw) > limit:
        raise ValueError("event store exceeds its bound")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".native-event-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _root() -> Path:
    if not settings.native_event_store_path:
        raise NativeEventsUnavailable("Native events are not configured; set NATIVE_EVENT_STORE_PATH to a persistent absolute directory.")
    root = Path(settings.native_event_store_path)
    if not root.is_absolute():
        raise NativeEventsUnavailable("Native event storage requires an absolute directory.")
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


@contextmanager
def _file_lock(root: Path):
    # Nonblocking OS locks cover distinct workers; the asyncio lock covers this
    # process without blocking its event loop while the holder queries the DB.
    with (root / ".lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise NativeEventsUnavailable("Native event projection is busy; retry shortly.") from error
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _pointer(root: Path):
    path = root / "current.json"
    if not path.exists():
        if next(root.glob("generation.*.json"), None) is not None:
            raise ValueError("missing event pointer; explicit recovery required")
        return None
    value = _read(path, MAX_POINTER)
    generations = value.get("generations")
    if value.get("schema_version") != 1 or not isinstance(generations, list) or not 1 <= len(generations) <= 3:
        raise ValueError("invalid event pointer")
    if any(not isinstance(sid, str) or not GENERATION.fullmatch(sid) for sid in generations) or len(set(generations)) != len(generations):
        raise ValueError("invalid retained generations")
    if value.get("current") != generations[0]:
        raise ValueError("invalid current generation")
    return value


def _bundle(root: Path, sid: str):
    value = _read(root / ("generation." + sid + ".json"), MAX_BUNDLE)
    news, index, health = value["news"], value["events"], value["health"]
    validate_registry(value["registry"])
    if news.get("schema_version") != 1 or news.get("snapshot_id") != sid or _digest(news) != news.get("content_sha256") or _generation(news) != sid:
        raise ValueError("corrupt event generation")
    for report in (index, health):
        if any(report.get(key) != news.get(key) for key in ("snapshot_id", "generated_at", "content_sha256")):
            raise ValueError("event generation binding mismatch")
    articles = {row["article_id"]: row for row in news["articles"]}
    members = [item for event in index["events"] for item in event["article_ids"]]
    if len(articles) != len(news["articles"]) or len(members) != len(set(members)) or set(members) != set(articles):
        raise ValueError("incomplete event coverage")
    ids = {event["event_id"] for event in index["events"]}
    for event in index["events"]:
        publishers = {articles[item]["source"]["publisher_id"] for item in event["article_ids"]}
        if event["article_count"] != len(event["article_ids"]) or event["publisher_count"] != len(publishers) or set(event["publisher_ids"]) != publishers:
            raise ValueError("inconsistent event evidence")
        if any(articles[item]["event_id"] != event["event_id"] for item in event["article_ids"]):
            raise ValueError("event assignment mismatch")
    for old, current in index.get("aliases", {}).items():
        if not EVENT.fullmatch(old) or old in ids or current not in ids:
            raise ValueError("invalid current event alias")
    return value


def _publisher(source: Source) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", source.publisher).casefold().split())
    return "p_" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]


def _public_source(source: Source) -> dict:
    value = SourceResponse.model_validate(source).model_dump(mode="json")
    value["publisher_id"] = _publisher(source)
    return value


async def _project(db: AsyncSession, root: Path):
    pointer = _pointer(root)
    previous = _bundle(root, pointer["current"]) if pointer else None
    marker = await db.get(SyncState, "worker:last_sync_at")
    if marker is None or not marker.value:
        raise NativeEventsUnavailable("Native news has no completed worker timestamp.")
    completed = _timestamp(marker.value)
    now = datetime.now(timezone.utc)
    if completed > now + timedelta(minutes=5) or completed < now - timedelta(hours=72):
        raise NativeEventsUnavailable("Native news is expired or its completed timestamp is invalid.")
    generated_at = completed.isoformat().replace("+00:00", "Z")
    source_rows = (await db.scalars(select(Source).where(Source.enabled.is_(True)).order_by(Source.id))).all()
    sources = [_public_source(source) for source in source_rows]
    healthy = sum(source.health_status == "ok" for source in source_rows)
    query = (select(Article).join(Article.source).options(contains_eager(Article.source))
        .where(Source.enabled.is_(True), Article.published_at >= completed - timedelta(hours=72),
            Article.published_at <= completed, Article.fetched_at <= completed)
        .order_by(Article.published_at.desc(), Article.id.desc()).limit(MAX_ARTICLES + 1))
    rows = (await db.scalars(query)).all()
    if not rows or not healthy:
        raise NativeEventsUnavailable("Native events require recent articles and at least one healthy enabled source.")
    articles = []
    for row in rows[:MAX_ARTICLES]:
        value = ArticleResponse.model_validate(row).model_dump(mode="json")
        value["source"] = _public_source(row.source)
        articles.append(value)
    # Do not seal a generation if the completed sync advanced while reading it.
    await db.refresh(marker)
    if _timestamp(marker.value) != completed:
        raise NativeEventsUnavailable("Native news changed during projection; retry shortly.")
    index, registry = await asyncio.to_thread(build_event_index, articles, generated_at, previous["registry"] if previous else None)
    await db.refresh(marker)
    if _timestamp(marker.value) != completed:
        raise NativeEventsUnavailable("Native news changed during projection; retry shortly.")
    active = {event["event_id"] for event in index["events"]}
    index["aliases"] = {old: current for old, current in index.get("aliases", {}).items() if current in active and old not in active}
    health = {"configured": len(sources), "healthy": healthy, "failed": len(sources) - healthy,
        "gate_pass": True, "gate_kind": "native-database-projection", "production_acceptance": False}
    news = {"schema_version": 1, "generated_at": generated_at, "articles": articles, "sources": sources,
        "health": health, "meta": {"version": settings.app_version, "regions": sorted({s["region"] for s in sources}),
            "categories": sorted({s["category"] for s in sources}), "languages": sorted({s["language"] for s in sources}),
            "source_count": len(sources), "article_count": len(articles), "last_sync_at": generated_at,
            "publication_mode": "snapshot", "data_origin": "native-database", "article_limit": MAX_ARTICLES,
            "article_limit_reached": len(rows) > MAX_ARTICLES, "formal_release": False}}
    news["generation_method"] = "native-version-bound-v1"
    news["content_sha256"] = _digest(news)
    sid = _generation(news)
    news.update(snapshot_id=sid, events_file="events." + sid + ".json", source_health_file="source-health." + sid + ".json")
    binding = {key: news[key] for key in ("snapshot_id", "generated_at", "content_sha256")}
    index.update(binding)
    report = {"schema_version": 1, **binding, "health": health, "sources": sources,
        "publication_mode": "native-database", "formal_release": False}
    bundle = {"news": news, "events": index, "health": report, "registry": registry}
    if pointer and sid == pointer["current"]:
        return previous
    path = root / ("generation." + sid + ".json")
    if path.exists():
        # An interrupted pointer update can leave a fully sealed generation.
        bundle = _bundle(root, sid)
    else:
        _atomic(path, bundle, MAX_BUNDLE)
        bundle = _bundle(root, sid)
    retained = [sid] + [old for old in pointer["generations"] if old != sid][:2] if pointer else [sid]
    _atomic(root / "current.json", {"schema_version": 1, "current": sid, "generations": retained}, MAX_POINTER)
    for old in root.glob("generation.*.json"):
        old_sid = old.name[len("generation."):-len(".json")]
        if GENERATION.fullmatch(old_sid) and old_sid not in retained:
            old.unlink()
    return bundle


async def native_bundle(db: AsyncSession):
    try:
        async with _lock:
            root = _root()
            with _file_lock(root):
                return await _project(db, root)
    except NativeEventsUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise NativeEventsUnavailable("Native event state is invalid or unavailable; explicit storage recovery may be required.") from error


async def native_asset(sid: str, name: str):
    if not GENERATION.fullmatch(sid) or name not in ("events." + sid + ".json", "source-health." + sid + ".json"):
        return None
    try:
        async with _lock:
            root = _root()
            with _file_lock(root):
                pointer = _pointer(root)
                if not pointer or sid not in pointer["generations"]:
                    return None
                value = _bundle(root, sid)
                return value["events" if name.startswith("events.") else "health"]
    except NativeEventsUnavailable:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        raise NativeEventsUnavailable("Native event state is invalid or unavailable; explicit storage recovery may be required.") from error
