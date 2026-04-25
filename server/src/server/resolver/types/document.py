"""Document entity type — policies, invoices, contracts, anything PDF-like."""

from __future__ import annotations

from typing import Any

ENTITY_TYPE = "document"
HARD_ID_FIELDS = ["source_uri", "doc_id"]


def extract_hard_ids(attrs: dict[str, Any]) -> dict[str, str]:
    return {k: str(v).lower() for k, v in attrs.items() if k in HARD_ID_FIELDS and v}


def build_search_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for k in ("title", "doc_type", "scope", "issued_by", "category"):
        if v := attrs.get(k):
            parts.append(str(v))
    return " | ".join(parts)


def extract_context_signals(attrs: dict[str, Any]) -> dict[str, str]:
    """Documents currently have no domain-style hints (no canonical company link)."""
    return {}
