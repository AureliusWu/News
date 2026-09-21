"""Live read-only smoke evidence; no fixtures and no production database writes."""
import argparse
import asyncio
import json
import re
import statistics
import time
from datetime import timedelta

import httpx
from sqlalchemy import func, select

from app.core.db import SessionLocal, engine
from app.models import Article, Source, SyncState, utcnow
from app.services.miniflux_client import MinifluxClient
from app.services.news_normalizer import canonicalize_url, parse_datetime, safe_url


async def verify(base_url):
    result = {"checked_at": utcnow().isoformat(), "base_url": base_url, "checks": {}, "samples": []}
    client = MinifluxClient()
    try:
        async with SessionLocal() as db:
            total = await db.scalar(select(func.count(Article.id)))
            unique = await db.scalar(select(func.count(func.distinct(Article.canonical_hash))))
            latest = await db.scalar(select(func.max(Article.published_at)))
            recent = {}
            for hours in (1, 6, 24):
                recent[str(hours) + "h"] = await db.scalar(select(func.count(Article.id)).where(Article.published_at >= utcnow() - timedelta(hours=hours)))
            result["database"] = {"article_count": total, "unique_canonical_urls": unique,
                "latest_article": latest.isoformat() if latest else None, "recent": recent}
            result["checks"]["database_has_real_volume"] = total >= 100
            result["checks"]["no_duplicate_urls"] = total == unique
            result["checks"]["freshness"] = latest is not None and latest >= utcnow() - timedelta(hours=6)
            states = (await db.scalars(select(SyncState))).all()
            result["watermarks"] = {s.key: s.value for s in states}
            async with httpx.AsyncClient(base_url=base_url, timeout=15) as web:
                paths = ["/", "/api/v1/health", "/api/v1/news", "/api/v1/news?region=world",
                    "/api/v1/news?category=technology&limit=10", "/api/v1/sources", "/api/v1/meta",
                    "/manifest.webmanifest", "/sw.js"]
                result["http"] = {}
                for path in paths:
                    start = time.monotonic()
                    response = await web.get(path)
                    result["http"][path] = {"status": response.status_code,
                        "ms": round((time.monotonic() - start) * 1000, 2), "content_type": response.headers.get("content-type")}
                    result["checks"]["http " + path] = response.status_code == 200
                times = []
                for _ in range(5):
                    start = time.monotonic()
                    response = await web.get("/api/v1/news?limit=30")
                    response.raise_for_status()
                    times.append(round((time.monotonic() - start) * 1000, 2))
                result["performance"] = {"samples_ms": times, "median_ms": statistics.median(times), "worst_ms": max(times)}
                result["checks"]["api_latency_under_3s"] = max(times) < 3000
                page = (await web.get("/api/v1/news?limit=30")).json()
                if page["has_more"]:
                    second = (await web.get("/api/v1/news", params={"cursor": page["next_cursor"], "limit": 30})).json()
                    result["checks"]["cursor_disjoint"] = not ({a["id"] for a in page["items"]} & {a["id"] for a in second["items"]})
                result["checks"]["invalid_cursor_400"] = (await web.get("/api/v1/news?cursor=invalid")).status_code == 400
                result["checks"]["sample_count_20"] = len(page["items"]) >= 20
                for item in page["items"][:20]:
                    article = await db.get(Article, item["id"])
                    response = await client.request("GET", "/v1/entries/" + str(article.miniflux_entry_id))
                    origin = response.json()
                    matched = canonicalize_url(origin["url"]) == article.canonical_url and parse_datetime(origin["published_at"]) == article.published_at
                    clean = not re.search(r"<(?:p|div|script|style|img)\b", item["summary"] or "", re.I)
                    fields_ok = bool(item["title"].strip() and safe_url(item["url"]) and item["source"]["name"] and clean)
                    result["samples"].append({"article_id": article.id, "miniflux_entry_id": article.miniflux_entry_id,
                        "title": item["title"], "url": item["url"], "source": item["source"]["name"],
                        "published_at": item["published_at"], "has_image": bool(item["image_url"]),
                        "lineage_match": matched, "fields_ok": fields_ok})
                result["checks"]["sample_lineage"] = all(s["lineage_match"] and s["fields_ok"] for s in result["samples"]) and len(result["samples"]) == 20
                source_payload = (await web.get("/api/v1/sources")).json()
                result["checks"]["no_internal_source_fields"] = all(not {"feed_url", "miniflux_feed_id", "last_error", "password"} & set(s) for s in source_payload)
        result["pass"] = all(result["checks"].values())
        return result
    finally:
        await client.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://frontend")
    result = asyncio.run(verify(parser.parse_args().base_url))
    print(json.dumps(result, ensure_ascii=True, indent=2))
    raise SystemExit(0 if result["pass"] else 1)