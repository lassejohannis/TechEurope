"""Opaque cursor-pagination helpers.

Cursor format: `base64url(json({"ts": <iso>, "id": <id>}))`. Stable across page
turns; clients treat it as opaque. Use with keyset queries: `where (ts,id) <
(cursor.ts, cursor.id) order by ts desc, id desc`.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Cursor:
    ts: str
    id: str

    def encode(self) -> str:
        raw = json.dumps({"ts": self.ts, "id": self.id}, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(value: str | None) -> Cursor | None:
    if not value:
        return None
    try:
        padding = "=" * (-len(value) % 4)
        raw = base64.urlsafe_b64decode(value + padding).decode()
        data = json.loads(raw)
        return Cursor(ts=str(data["ts"]), id=str(data["id"]))
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def build_page(rows: list[dict[str, Any]], limit: int, *, ts_key: str, id_key: str) -> dict[str, Any]:
    """Slice a `limit+1` query into a `{items, next_cursor}` page envelope."""
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor: str | None = None
    if has_more and items:
        last = items[-1]
        next_cursor = Cursor(ts=str(last[ts_key]), id=str(last[id_key])).encode()
    return {"items": items, "next_cursor": next_cursor, "count": len(items)}
