import hashlib
import re
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "utm_id", "fbclid", "gclid"}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1
        if tag in {"p", "div", "br", "li", "h1", "h2"}:
            self.parts.append(" ")
        if tag == "img":
            self.images.append(dict(attrs).get("src", ""))

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "li", "h1", "h2"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def strip_html(raw: str | None) -> str | None:
    parser = PlainText()
    parser.feed(raw or "")
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip() or None


def safe_url(value: str | None) -> str | None:
    try:
        parsed = urlsplit(value or "")
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return None
        if any(c.isspace() for c in value or ""):
            return None
        return value
    except ValueError:
        return None


def canonicalize_url(url: str | None) -> str:
    if not safe_url(url):
        raise ValueError("Article URL must be HTTP(S) without credentials")
    p = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in TRACKING]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or "/", urlencode(query), ""))


def extract_summary(raw: str | None, max_len: int = 280) -> str | None:
    value = strip_html(raw)
    return (value[:max_len - 3].rstrip() + "...") if value and len(value) > max_len else value


def first_image_url(entry: dict) -> str | None:
    for enclosure in entry.get("enclosures") or []:
        if str(enclosure.get("mime_type", "")).startswith("image/"):
            candidate = safe_url(enclosure.get("url"))
            if candidate:
                return candidate
    parser = PlainText()
    parser.feed(entry.get("content") or "")
    for src in parser.images:
        candidate = safe_url(urljoin(entry.get("url") or "", src or "")) if src else None
        if candidate:
            return candidate
    return None


def parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str):
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    else:
        raise ValueError("Missing publication date")
    if dt.tzinfo is None:
        raise ValueError("Publication date must include a timezone")
    dt = dt.astimezone(timezone.utc)
    if dt.year < 2000 or dt > datetime.now(timezone.utc) + timedelta(hours=1):
        raise ValueError("Implausible publication date")
    return dt


def entry_hash(entry: dict) -> str:
    return str(entry.get("hash") or hashlib.sha256(str(entry.get("url", "")).encode()).hexdigest())[:255]


def normalize_entry(source, entry: dict) -> dict:
    canonical = canonicalize_url(entry.get("url"))
    title = strip_html(entry.get("title"))
    if not title or int(entry["id"]) <= 0:
        raise ValueError("Entry needs title and positive ID")
    return dict(source_id=source.id, miniflux_entry_id=int(entry["id"]), external_id=None,
                miniflux_hash=entry_hash(entry), url=entry["url"], canonical_url=canonical,
                canonical_hash=hashlib.sha256(canonical.encode()).hexdigest(), title=title[:500],
                author=(strip_html(entry.get("author")) or "")[:255] or None,
                summary=extract_summary(entry.get("content") or entry.get("summary")),
                content_html=entry.get("content") or None, image_url=first_image_url(entry),
                language=source.language, region=source.region, category=source.category,
                published_at=parse_datetime(entry.get("published_at")))