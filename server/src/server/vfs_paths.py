"""Shared VFS path helpers.

Centralizes:
1) slug generation for canonical names
2) entity_type <-> path segment mapping
3) glob-pattern conversion for SQL ILIKE filters
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from server.db import get_db


_CONFIG_SLUG_KEYS = (
    "vfs_slug",
    "path_slug",
    "slug",
    "collection",
    "plural",
)


def slugify_name(value: str) -> str:
    """Lowercase + non-alphanumeric → '-' slugify.

    Strips a leading `<known_type>:` prefix first because some extractors
    (notably Pioneer's GLiNER2) emit canonical_name as a fully-qualified
    entity id like `person:jane-doe` instead of just `Jane Doe`. Without
    this strip we end up with VFS paths like `/persons/person:jane-doe`.
    The list is sourced from the approved entity_type_config rows so it
    grows with the autonomous-ontology evolution.
    """
    if isinstance(value, str) and ":" in value:
        head, tail = value.split(":", 1)
        try:
            _, type_to_slug = get_type_slug_maps()
            if head in type_to_slug:
                value = tail
        except Exception:
            # Cache not loadable yet — skip the strip; downstream still
            # produces a valid slug even with the prefix included.
            pass
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unnamed"


def pluralize_entity_type(entity_type: str) -> str:
    if entity_type.endswith("y") and len(entity_type) > 1 and entity_type[-2] not in "aeiou":
        return f"{entity_type[:-1]}ies"
    if entity_type.endswith(("s", "x", "z", "ch", "sh")):
        return f"{entity_type}es"
    return f"{entity_type}s"


def singularize_segment(segment: str) -> str:
    if segment.endswith("ies") and len(segment) > 3:
        return f"{segment[:-3]}y"
    if segment.endswith("es") and len(segment) > 2:
        return segment[:-2]
    if segment.endswith("s") and len(segment) > 1:
        return segment[:-1]
    return segment


def _slug_from_cfg(entity_type: str, cfg: dict[str, Any]) -> str:
    for key in _CONFIG_SLUG_KEYS:
        value = cfg.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip().strip("/")
    return pluralize_entity_type(entity_type)


@lru_cache(maxsize=1)
def get_type_slug_maps() -> tuple[dict[str, str], dict[str, str]]:
    """Return (slug_to_type, type_to_slug) from entity_type_config.

    Falls back to heuristic pluralization if config does not contain dedicated
    VFS slug keys.
    """
    try:
        db = get_db()
        res = db.table("entity_type_config").select("id, config").execute()
        rows = res.data or []
    except Exception:
        rows = []

    type_to_slug: dict[str, str] = {}
    for row in rows:
        entity_type = str(row.get("id") or "").strip()
        if not entity_type:
            continue
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        type_to_slug[entity_type] = _slug_from_cfg(entity_type, cfg)

    slug_to_type = {slug: entity_type for entity_type, slug in type_to_slug.items()}
    return slug_to_type, type_to_slug


def type_from_segment(segment: str) -> str:
    try:
        slug_to_type, _ = get_type_slug_maps()
        if segment in slug_to_type:
            return slug_to_type[segment]
    except Exception:
        pass
    return singularize_segment(segment)


def segment_from_type(entity_type: str) -> str:
    try:
        _, type_to_slug = get_type_slug_maps()
        return type_to_slug.get(entity_type, pluralize_entity_type(entity_type))
    except Exception:
        return pluralize_entity_type(entity_type)


def glob_to_ilike(pattern: str) -> str:
    """Convert a VFS glob pattern to a SQL ILIKE pattern.

    Supports `*` and `**` (both mapped to `%` in SQL).
    """
    p = pattern.strip()
    if not p:
        return "%"
    if not p.startswith("/"):
        p = f"/{p}"
    return p.replace("**", "%").replace("*", "%")
