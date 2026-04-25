"""Person entity type — hard-ID fields and context heuristics."""

from __future__ import annotations

from typing import Any

ENTITY_TYPE = "person"
HARD_ID_FIELDS = ["emp_id", "email"]


def extract_hard_ids(attrs: dict[str, Any]) -> dict[str, str]:
    return {k: str(v).lower() for k, v in attrs.items() if k in HARD_ID_FIELDS and v}


def build_search_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for k in ("email", "emp_id", "department", "category"):
        if v := attrs.get(k):
            parts.append(str(v))
    return " | ".join(parts)


def extract_context_signals(attrs: dict[str, Any]) -> dict[str, str]:
    """email domain → employer company heuristic."""
    signals: dict[str, str] = {}
    email = str(attrs.get("email", ""))
    if "@" in email:
        signals["email_domain"] = email.rsplit("@", 1)[1].lower()
    return signals
