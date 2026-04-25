"""Company entity type — hard-ID fields and context heuristics."""

from __future__ import annotations

from typing import Any

ENTITY_TYPE = "company"
HARD_ID_FIELDS = ["tax_id", "domain"]


def extract_hard_ids(attrs: dict[str, Any]) -> dict[str, str]:
    return {k: str(v).lower() for k, v in attrs.items() if k in HARD_ID_FIELDS and v}


def build_search_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for k in ("industry", "domain", "tax_id", "registered_address"):
        if v := attrs.get(k):
            parts.append(str(v))
    return " | ".join(parts)


def extract_context_signals(attrs: dict[str, Any]) -> dict[str, str]:
    signals: dict[str, str] = {}
    if domain := attrs.get("domain"):
        signals["domain"] = str(domain).lower()
    return signals
