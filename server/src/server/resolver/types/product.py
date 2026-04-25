"""Product entity type — hard-ID fields."""

from __future__ import annotations

from typing import Any

ENTITY_TYPE = "product"
HARD_ID_FIELDS = ["product_id", "sku"]


def extract_hard_ids(attrs: dict[str, Any]) -> dict[str, str]:
    return {k: str(v).lower() for k, v in attrs.items() if k in HARD_ID_FIELDS and v}


def build_search_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for k in ("category", "product_id", "sku"):
        if v := attrs.get(k):
            parts.append(str(v))
    return " | ".join(parts)


def extract_context_signals(attrs: dict[str, Any]) -> dict[str, str]:
    return {}
