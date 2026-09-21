import asyncio
import random

import httpx

from app.core.config import settings


class MinifluxError(RuntimeError):
    pass


class MinifluxClient:
    def __init__(self, base_url=None, username=None, password=None, timeout=25.0, transport=None):
        self._client = httpx.AsyncClient(base_url=(base_url or settings.miniflux_url).rstrip("/"),
            auth=(username or settings.miniflux_admin_username, password or settings.miniflux_admin_password),
            timeout=httpx.Timeout(timeout, connect=8.0), transport=transport, headers={"Accept": "application/json"})

    async def aclose(self):
        await self._client.aclose()

    async def request(self, method, path, **kwargs):
        # POST creation is reconciled during bootstrap instead of blindly retried.
        attempts = 1 if method == "POST" else 3
        for attempt in range(attempts):
            try:
                response = await self._client.request(method, path, **kwargs)
                if response.status_code in {429, 502, 503, 504} and attempt + 1 < attempts:
                    await asyncio.sleep(0.5 * 2 ** attempt + random.uniform(0, 0.2))
                    continue
                if response.is_error:
                    raise MinifluxError(f"{method} {path}: HTTP {response.status_code}")
                return response
            except httpx.TransportError as exc:
                if attempt + 1 == attempts:
                    raise MinifluxError(f"{method} {path}: {type(exc).__name__}") from None
                await asyncio.sleep(0.5 * 2 ** attempt + random.uniform(0, 0.2))

    async def _json(self, method, path, expected, **kwargs):
        response = await self.request(method, path, **kwargs)
        try:
            result = response.json()
        except ValueError:
            raise MinifluxError(f"{path}: invalid JSON") from None
        if not isinstance(result, expected):
            raise MinifluxError(f"{path}: invalid response shape")
        return result

    async def healthcheck(self):
        return (await self.request("GET", "/healthcheck")).status_code == 200

    async def list_feeds(self):
        return await self._json("GET", "/v1/feeds", list)

    async def get_feed(self, feed_id):
        return await self._json("GET", f"/v1/feeds/{feed_id}", dict)

    async def create_feed(self, *, feed_url, category_id, crawler=False, user_agent=None):
        payload = dict(feed_url=feed_url, category_id=category_id, crawler=crawler)
        if user_agent:
            payload["user_agent"] = user_agent
        result = await self._json("POST", "/v1/feeds", dict, json=payload)
        if not isinstance(result.get("feed_id"), int) or result["feed_id"] <= 0:
            raise MinifluxError("create feed: missing ID")
        return result["feed_id"]

    async def update_feed(self, feed_id, payload):
        return await self._json("PUT", f"/v1/feeds/{feed_id}", dict, json=payload)

    async def refresh_all_feeds(self):
        await self.request("PUT", "/v1/feeds/refresh")

    async def refresh_feed(self, feed_id):
        await self.request("PUT", f"/v1/feeds/{feed_id}/refresh")

    async def discover_feed(self, url):
        return await self._json("POST", "/v1/discover", list, json={"url": url})

    async def get_feed_entries(self, feed_id, *, after_entry_id=None, limit=100, **filters):
        params = {"limit": limit, "order": "id", "direction": "asc", **filters}
        if after_entry_id is not None:
            params["after_entry_id"] = after_entry_id
        result = await self._json("GET", f"/v1/feeds/{feed_id}/entries", dict, params=params)
        entries = result.get("entries")
        if not isinstance(entries, list) or any(not isinstance(e, dict) or not isinstance(e.get("id"), int) or e["id"] <= 0 for e in entries):
            raise MinifluxError("entries: invalid shape")
        return result

    async def get_categories(self):
        return await self._json("GET", "/v1/categories", list)

    async def create_category(self, title):
        return int((await self._json("POST", "/v1/categories", dict, json={"title": title}))["id"])