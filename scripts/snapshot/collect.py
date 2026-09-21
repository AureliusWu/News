"""Build a gated, read-only public news snapshot from configured RSS feeds."""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import time
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import feedparser
import httpx
from bs4 import BeautifulSoup
import yaml

UTC = timezone.utc
MAX_FEED_BYTES = 4 * 1024 * 1024
TRACKING = {'fbclid', 'gclid', 'mc_cid', 'mc_eid', 'at_medium', 'at_campaign', 'traffic_source'}


def safe_url(value: str, base: str = '', *, https_only: bool = False) -> str | None:
    try:
        parts = urlsplit(urljoin(base, str(value or '').strip()))
        host = (parts.hostname or '').lower()
        if parts.scheme not in (('https',) if https_only else ('http', 'https')) or not host or parts.username or parts.password:
            return None
        if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal')) or '.' not in host:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        _ = parts.port
        query = urlencode([(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                           if not key.lower().startswith('utm_') and key.lower() not in TRACKING])
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or '/', query, ''))
    except (ValueError, TypeError):
        return None


def plain_text(value: str, limit: int) -> str:
    soup = BeautifulSoup(str(value or ''), 'html.parser')
    for element in soup(['script', 'style', 'iframe', 'object']):
        element.decompose()
    return re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()[:limit]


def public_source(raw: dict, number: int) -> dict:
    slug = raw.get('id') or raw.get('slug')
    required = ('name', 'publisher', 'region', 'language', 'category')
    if not slug or any(not raw.get(field) for field in required):
        raise ValueError('A source is missing required identity or attribution fields.')
    return {
        'id': number, 'slug': str(slug), **{field: str(raw[field]) for field in required},
        'homepage': str(raw.get('homepage') or raw.get('site_url') or ''),
        'country': str(raw.get('country') or ''),
        'source_type': str(raw.get('type') or raw.get('source_type') or 'official_rss'),
        'health_status': 'unknown', 'enabled': raw.get('enabled', True) is not False,
    }


def normalize(entry: dict, source: dict, feed_url: str, now: datetime) -> dict | None:
    # Never manufacture publication time from collection time or an updated date.
    published = entry.get('published_parsed')
    if not published:
        return None
    try:
        timestamp = datetime.fromtimestamp(calendar.timegm(published), UTC)
    except (ValueError, TypeError, OverflowError):
        return None
    if timestamp < now - timedelta(days=7) or timestamp > now + timedelta(hours=1):
        return None
    title = plain_text(entry.get('title', ''), 500)
    url = safe_url(entry.get('link', ''), feed_url)
    if not title or not entry.get('link') or not url:
        return None
    raw_summary = entry.get('summary') or next((item.get('value', '') for item in entry.get('content', [])), '')
    image_url = None
    candidates = list(entry.get('media_thumbnail', [])) + list(entry.get('media_content', []))
    candidates += [item for item in entry.get('enclosures', []) if str(item.get('type', '')).startswith('image/')]
    for candidate in candidates:
        image_url = safe_url(candidate.get('url') or candidate.get('href') or '', feed_url, https_only=True) if candidate.get('url') or candidate.get('href') else None
        if image_url:
            break
    if not image_url and raw_summary:
        image = BeautifulSoup(str(raw_summary), 'html.parser').find('img', src=True)
        if image:
            image_url = safe_url(image.get('src'), feed_url, https_only=True)
    return {
        'id': int(hashlib.sha256(url.encode()).hexdigest()[:13], 16),
        'title': title, 'summary': plain_text(raw_summary, 280), 'url': url,
        'image_url': image_url, 'source': source,
        'region': source['region'], 'language': source['language'], 'category': source['category'],
        'published_at': timestamp.isoformat().replace('+00:00', 'Z'),
    }


def download(client: httpx.Client, url: str) -> tuple[bytes, str]:
    for _ in range(6):
        if not safe_url(url):
            raise ValueError('Unsafe feed or redirect URL')
        with client.stream('GET', url) as response:
            if response.is_redirect:
                url = urljoin(str(response.url), response.headers.get('location', ''))
                continue
            response.raise_for_status()
            chunks, size = [], 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_FEED_BYTES:
                    raise ValueError('Feed exceeds size limit')
                chunks.append(chunk)
            return b''.join(chunks), str(response.url)
    raise ValueError('Too many feed redirects')


def fetch_source(raw: dict, number: int, now: datetime) -> tuple[dict, list[dict], dict]:
    source = public_source(raw, number)
    feed_url = str(raw.get('feed_url') or raw.get('url') or '')
    row = {'id': source['slug'], 'name': source['name'], 'publisher': source['publisher'],
           'region': source['region'], 'language': source['language'], 'feed_url': feed_url,
           'health': 'FAIL', 'entry_count': 0, 'latest_entry': None, 'notes': None}
    if not source['enabled']:
        source['health_status'] = 'disabled'; row['health'] = 'DISABLED'
        return source, [], row
    start = time.monotonic()
    try:
        if source['source_type'] != 'official_rss':
            raise ValueError('Free snapshot mode accepts official public RSS/Atom feeds only')
        with httpx.Client(timeout=httpx.Timeout(18, connect=8), follow_redirects=False,
                          headers={'User-Agent': 'GlobalNews/0.2 (+https://github.com/AureliusWu/News)',
                                   'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.5'}) as client:
            data, final_url = download(client, feed_url)
        parsed = feedparser.parse(data)
        if not parsed.entries:
            raise ValueError('Feed has no parseable entries')
        articles = [article for entry in parsed.entries[:300]
                    if (article := normalize(entry, source, final_url, now))]
        if not articles:
            raise ValueError('No valid articles with original publication dates within seven days')
        source['health_status'] = 'ok'; row['health'] = 'PASS'
        row['entry_count'] = len(articles)
        row['latest_entry'] = max(article['published_at'] for article in articles)
        if not source['homepage']:
            source['homepage'] = safe_url(parsed.feed.get('link', ''), final_url) or ''
        return source, articles, row
    except httpx.HTTPStatusError as error:
        row['notes'] = f'Upstream HTTP {error.response.status_code}'
    except httpx.HTTPError as error:
        row['notes'] = type(error).__name__
    except ValueError as error:
        row['notes'] = str(error)
    except Exception as error:
        row['notes'] = f'Feed parsing failed: {type(error).__name__}'
    finally:
        row['latency_ms'] = round((time.monotonic() - start) * 1000, 1)
    source['health_status'] = 'failed'
    return source, [], row


def build_snapshot(results: list[tuple[dict, list[dict], dict]], now: datetime) -> tuple[dict, dict]:
    sources = [item[0] for item in results]
    rows = [item[2] for item in results]
    unique = {}
    for _, articles, _ in results:
        for article in articles:
            previous = unique.get(article['url'])
            if previous is None or article['published_at'] > previous['published_at']:
                unique[article['url']] = article
    articles = sorted(unique.values(), key=lambda item: (item['published_at'], item['id']), reverse=True)[:2500]
    healthy = [source for source in sources if source['health_status'] == 'ok']
    publishers = sorted({source['publisher'] for source in healthy})
    regions = sorted({source['region'] for source in healthy})
    languages = sorted({source['language'] for source in healthy})
    latest = articles[0]['published_at'] if articles else None
    fresh = latest is not None and datetime.fromisoformat(latest.replace('Z', '+00:00')) >= now - timedelta(hours=6)
    checks = {
        'at_least_25_healthy_feeds': len(healthy) >= 25,
        'at_least_15_publishers': len(publishers) >= 15,
        'at_least_7_regions': len(regions) >= 7,
        'at_least_2_languages': len(languages) >= 2,
        'at_least_100_real_articles': len(articles) >= 100,
        'latest_publication_within_6_hours': fresh,
        'unique_article_ids': len({item['id'] for item in articles}) == len(articles),
    }
    summary = {'configured': len(sources), 'healthy': len(healthy),
               'failed': sum(source['health_status'] == 'failed' for source in sources),
               'publishers': len(publishers), 'regions': regions, 'languages': languages,
               'article_count': len(articles), 'latest_publication': latest,
               'gate_pass': all(checks.values())}
    generated = now.isoformat().replace('+00:00', 'Z')
    report = {'checked_at': generated, 'mode': 'github-pages-snapshot', 'summary': summary, 'checks': checks, 'sources': rows}
    digest = hashlib.sha256(json.dumps({'articles': articles, 'sources': sources}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    snapshot = {
        'schema_version': 1, 'generated_at': generated, 'content_sha256': digest,
        'articles': articles, 'sources': sources, 'health': summary,
        'meta': {'version': '0.2.0', 'publication_mode': 'snapshot',
                 'regions': sorted({source['region'] for source in sources}),
                 'categories': sorted({source['category'] for source in sources}),
                 'languages': sorted({source['language'] for source in sources}),
                 'source_count': len(sources), 'article_count': len(articles), 'last_sync_at': generated},
    }
    return snapshot, report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--sources', default='config/sources.yaml')
    parser.add_argument('--output', default='frontend/public/data')
    parser.add_argument('--report', default='artifacts/pages-source-health.json')
    args = parser.parse_args()
    raw = yaml.safe_load(Path(args.sources).read_text(encoding='utf-8'))
    definitions = raw['sources'] if isinstance(raw, dict) else raw
    if not isinstance(definitions, list) or not definitions:
        raise ValueError('Source configuration is empty or invalid')
    now = datetime.now(UTC)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda pair: fetch_source(pair[1], pair[0] + 1, now), enumerate(definitions)))
    snapshot, report = build_snapshot(results, datetime.now(UTC))
    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'checked_at': report['checked_at'], 'summary': report['summary'], 'checks': report['checks'],
                      'failed_sources': [row for row in report['sources'] if row['health'] == 'FAIL']}, ensure_ascii=True, indent=2))
    if not report['summary']['gate_pass']:
        print('Publication blocked: retain the previous successfully deployed snapshot.')
        return 1
    payload = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(payload) > 8 * 1024 * 1024:
        raise ValueError('Snapshot exceeds the 8 MiB publication budget')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    temporary = output / 'news.json.tmp'
    temporary.write_bytes(payload)
    temporary.replace(output / 'news.json')
    (output / 'source-health.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Published candidate: {len(snapshot["articles"])} articles, {len(payload)} bytes; no full article bodies stored.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
