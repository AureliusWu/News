import base64
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock

from app.services.cursor import decode_cursor, encode_cursor
from app.services.miniflux_client import MinifluxClient, MinifluxError
from app.services.news_normalizer import canonicalize_url, extract_summary, first_image_url, normalize_entry, parse_datetime, strip_html
from app.services.source_registry import SourceDefinition, SourcesFile, SourceEntryError, load_sources


def definition(**overrides):
    return dict(id="bbc-world", name="BBC", publisher="BBC", homepage="https://www.bbc.com", country="GB",
        region="world", language="en", category="world", feed_url="https://feeds.bbci.co.uk/news/world/rss.xml", **overrides)


@pytest.mark.parametrize("raw,expected", [
    (" <p>Hello <b>world</b></p><p>Again</p> ", "Hello world Again"),
    ("<script>bad()</script><p>Safe &amp; sound</p>", "Safe & sound"),
    ("中文   日本語\n News", "中文 日本語 News"),
    ("<style>body{}</style>", None), ("", None), (None, None)
])
def test_plain_text(raw, expected):
    assert strip_html(raw) == expected


def test_excerpt_is_bounded_and_not_html():
    summary = extract_summary("<p>" + "word " * 100 + "</p>")
    assert len(summary) <= 280 and summary.endswith("...")
    assert "<p>" not in summary


@pytest.mark.parametrize("query,expected", [
    ("id=99&utm_source=mail&fbclid=tracking", "id=99"),
    ("article_id=8&gclid=x&page=2", "article_id=8&page=2"),
    ("id=1&id=2&ref=edition", "id=1&id=2&ref=edition"),
    ("UTM_CAMPAIGN=test&x=", "x=")
])
def test_tracking_removal_preserves_identifiers(query, expected):
    assert canonicalize_url("https://EXAMPLE.org/news?" + query + "#section") == "https://example.org/news?" + expected


@pytest.mark.parametrize("url", ["javascript:alert(1)", "file:///tmp/test", "https://user:secret@example.org", "", None])
def test_bad_article_url(url):
    with pytest.raises(ValueError):
        canonicalize_url(url)


def test_dates_are_utc():
    assert parse_datetime("2026-01-02T08:00:00+08:00") == datetime(2026, 1, 2, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, "", "bad", "2026-01-02", "1970-01-01T00:00:00Z", "2999-01-01T00:00:00Z"])
def test_invalid_date_is_not_replaced_with_now(value):
    with pytest.raises(ValueError):
        parse_datetime(value)


def test_image_priority_and_safe_schemes():
    entry = {"url": "https://example.org/news", "enclosures": [
        {"mime_type": "audio/mp3", "url": "https://example.org/audio.mp3"},
        {"mime_type": "image/png", "url": "javascript:bad"},
        {"mime_type": "image/jpeg", "url": "https://example.org/photo.jpg"}],
        "content": '<img src="/other.jpg">'}
    assert first_image_url(entry) == "https://example.org/photo.jpg"
    entry["enclosures"] = []
    assert first_image_url(entry) == "https://example.org/other.jpg"
    entry["content"] = '<img src="data:image/png;base64,aaa">'
    assert first_image_url(entry) is None


def test_normalize_keeps_unicode_and_nulls():
    source = SimpleNamespace(id=1, region="japan", language="ja", category="world")
    fields = normalize_entry(source, {"id": 1, "title": " 日本語   中文 ", "url": "https://example.org/1",
        "published_at": datetime.now(timezone.utc).isoformat()})
    assert fields["title"] == "日本語 中文"
    assert fields["summary"] is None and fields["image_url"] is None
    assert fields["language"] == "ja"


def test_registry_valid_disabled():
    source = SourceDefinition(**definition(enabled=False))
    assert not source.enabled


@pytest.mark.parametrize("field,value", [("feed_url", "bad"), ("homepage", "bad"), ("region", "moon"), ("id", "bad id")])
def test_registry_rejects_invalid_fields(field, value):
    payload = definition()
    payload[field] = value
    with pytest.raises(ValidationError):
        SourceDefinition(**payload)


def test_registry_duplicate():
    with pytest.raises(ValidationError):
        SourcesFile(sources=[SourceDefinition(**definition()), SourceDefinition(**definition())])


def test_registry_missing_file(tmp_path):
    with pytest.raises(SourceEntryError):
        load_sources(tmp_path / "missing.yaml")


def test_rsshub_path_validation():
    payload = definition()
    payload.update(source_type="rsshub", feed_url="", rsshub_path="//outside.example")
    with pytest.raises(ValidationError):
        SourceDefinition(**payload)


def test_cursor_roundtrip():
    date = datetime.now(timezone.utc)
    assert decode_cursor(encode_cursor(date, 7)) == (date, 7)


@pytest.mark.parametrize("cursor", ["", "%", "not-json", "a"*513, "W10", "e30"])
def test_invalid_cursor(cursor):
    with pytest.raises(ValueError):
        decode_cursor(cursor)


@pytest.mark.parametrize("item_id", [-1, True, "1", 2**64])
def test_cursor_rejects_bad_identifier(item_id):
    cursor = base64.urlsafe_b64encode(json.dumps({"published_at": "2026-01-01T00:00:00Z", "id": item_id}).encode()).decode()
    with pytest.raises(ValueError):
        decode_cursor(cursor)


async def test_miniflux_json_auth_and_discover():
    def handler(request):
        assert request.headers["authorization"].startswith("Basic ")
        assert request.headers["content-type"] == "application/json"
        if request.url.path == "/v1/discover":
            return httpx.Response(200, json=[{"url": "https://example.org/feed"}])
        return httpx.Response(201, json={"feed_id": 42})
    client = MinifluxClient("https://miniflux.test", "user", "secret", transport=httpx.MockTransport(handler))
    try:
        assert await client.create_feed(feed_url="https://example.org/feed", category_id=1) == 42
        assert (await client.discover_feed("https://example.org"))[0]["url"].endswith("/feed")
    finally:
        await client.aclose()


async def test_miniflux_timeout_retries_and_redacts(monkeypatch):
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("password=do-not-log", request=request)
    monkeypatch.setattr("app.services.miniflux_client.asyncio.sleep", AsyncMock())
    client = MinifluxClient("https://miniflux.test", transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MinifluxError, match="ReadTimeout") as exc:
            await client.list_feeds()
        assert calls == 3 and "do-not-log" not in str(exc.value)
    finally:
        await client.aclose()


async def test_miniflux_shape_validation():
    client = MinifluxClient("https://miniflux.test", transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"entries": "wrong"})))
    try:
        with pytest.raises(MinifluxError):
            await client.get_feed_entries(1)
    finally:
        await client.aclose()