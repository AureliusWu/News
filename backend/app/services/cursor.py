import base64
import json
import re
from datetime import datetime, timezone


def encode_cursor(published_at: datetime, item_id: int) -> str:
    dt = published_at.replace(tzinfo=timezone.utc) if published_at.tzinfo is None else published_at.astimezone(timezone.utc)
    raw = json.dumps({"published_at": dt.isoformat(), "id": item_id}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,512}={0,2}", cursor):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        dt = datetime.fromisoformat(payload["published_at"])
        item_id = payload["id"]
        if dt.tzinfo is None or type(item_id) is not int or not 0 < item_id < 2 ** 63:
            raise ValueError()
        return dt.astimezone(timezone.utc), item_id
    except (ValueError, KeyError, TypeError, UnicodeError) as exc:
        raise ValueError("Invalid cursor") from exc