"""Read-only verification against the real Miniflux instance, with an optional Markdown report."""
import argparse
import asyncio
import json
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal, engine
from app.models import Source, utcnow
from app.services.miniflux_client import MinifluxClient, MinifluxError
from app.services.news_normalizer import parse_datetime
from app.services.source_registry import load_sources


async def collect_health():
    definitions = load_sources(settings.source_registry_path)
    async with SessionLocal() as db:
        registered = {s.slug: s for s in (await db.scalars(select(Source))).all()}
    client = MinifluxClient()
    semaphore = asyncio.Semaphore(4)
    try:
        feeds = {f["id"]: f for f in await client.list_feeds()}
        async def check(definition):
            async with semaphore:
                started = time.monotonic()
                row = {"id": definition.id, "name": definition.name, "publisher": definition.publisher,
                    "region": definition.region, "category": definition.category, "language": definition.language,
                    "type": definition.source_type, "feed_url": definition.feed_url, "health": "FAIL",
                    "latest_entry": None, "entry_count": 0, "notes": "", "latency_ms": None}
                if not definition.enabled:
                    row.update(health="DISABLED", notes=definition.notes or "Disabled in registry")
                    return row
                source = registered.get(definition.id)
                feed = feeds.get(source.miniflux_feed_id) if source else None
                if not feed:
                    row["notes"] = source.last_error if source else "Not bootstrapped"
                    return row
                try:
                    data = await client.get_feed_entries(feed["id"], limit=1, order="published_at", direction="desc")
                    row["entry_count"] = data.get("total", 0)
                    if data["entries"]:
                        date = parse_datetime(data["entries"][0].get("published_at"))
                        row["latest_entry"] = date.isoformat()
                    if feed.get("parsing_error_count", 0):
                        row["notes"] = "Miniflux parsing errors: " + str(feed["parsing_error_count"])
                    elif not row["latest_entry"]:
                        row.update(health="WARN", notes="No entries")
                    elif parse_datetime(row["latest_entry"]) < utcnow() - timedelta(days=7):
                        row.update(health="WARN", notes="Newest entry is older than seven days")
                    else:
                        row.update(health="PASS", notes="Parsed successfully; recent entry present")
                except (MinifluxError, ValueError) as exc:
                    row["notes"] = str(exc)
                row["latency_ms"] = round((time.monotonic() - started) * 1000, 1)
                return row
        rows = await asyncio.gather(*(check(d) for d in definitions))
    finally:
        await client.aclose()
    good = [row for row in rows if row["health"] == "PASS"]
    counts = Counter(row["health"] for row in rows)
    summary = {"configured": len(rows), "healthy": len(good), "warning": counts["WARN"], "failed": counts["FAIL"],
        "disabled": counts["DISABLED"], "publishers": len({r["publisher"] for r in good}),
        "regions": sorted({r["region"] for r in good}), "languages": sorted({r["language"] for r in good}),
        "official_rss": sum(r["type"] == "official_rss" for r in good), "rsshub": sum(r["type"] == "rsshub" for r in good)}
    summary["gate_pass"] = summary["healthy"] >= 25 and summary["publishers"] >= 15 and len(summary["regions"]) >= 7 and len(summary["languages"]) >= 2
    return {"checked_at": utcnow().isoformat(), "summary": summary, "sources": rows}


def markdown(report):
    def clean(value):
        return str(value if value is not None else "n/a").replace("|", "/").replace("\n", " ")
    summary = report["summary"]
    lines = ["# V0.2 Source Health", "", "Checked at (UTC): " + report["checked_at"], "",
        "Read-only live validation: registry -> registered feed -> Miniflux parsing state and most recent entry.",
        "PASS requires a parsed feed with an entry published within seven days. Publisher identities are grouped explicitly, not counted per channel.",
        "", "## Coverage", "", *("- " + key + ": " + clean(value) for key, value in summary.items()), "",
        "## Feed results", "",
        "| Source | Publisher | Region | Category | Language | Type | Health | Latest entry (UTC) | Entries | API ms | Notes |",
        "|---|---|---|---|---|---|---|---|---:|---:|---|"]
    for row in report["sources"]:
        lines.append("| " + " | ".join(clean(row[k]) for k in ["name", "publisher", "region", "category", "language", "type", "health", "latest_entry", "entry_count", "latency_ms", "notes"]) + " |")
    lines += ["", "Latency measures the internal Miniflux API, not the original publisher's network latency.",
        "Failed and disabled sources are retained here for transparency. A valid URL alone does not count as healthy.", ""]
    return "\n".join(lines)


async def main(report_path=None):
    try:
        report = await collect_health()
        if report_path:
            Path(report_path).write_text(markdown(report), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=True, indent=2))
        return 0 if report["summary"]["gate_pass"] else 1
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", help="Optional Markdown output path")
    raise SystemExit(asyncio.run(main(parser.parse_args().report)))