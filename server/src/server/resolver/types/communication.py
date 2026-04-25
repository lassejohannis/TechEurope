"""Communication entity type — first-class node for emails, tickets, chat threads.

Every email thread and IT ticket becomes a single Communication entity with
participant_in / authored / assigned_to edges to the People involved. This is
what makes the Graph dense — without it Persons just hang off Companies
with works_at edges.
"""

from __future__ import annotations

from typing import Any

ENTITY_TYPE = "communication"
HARD_ID_FIELDS = ["thread_id", "email_id", "ticket_id", "conversation_id"]


def extract_hard_ids(attrs: dict[str, Any]) -> dict[str, str]:
    return {k: str(v).lower() for k, v in attrs.items() if k in HARD_ID_FIELDS and v}


def build_search_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for k in ("subject", "channel", "category", "topic", "ticket_id"):
        if v := attrs.get(k):
            parts.append(str(v))
    return " | ".join(parts)


def extract_context_signals(attrs: dict[str, Any]) -> dict[str, str]:
    """Communications have no domain-side heuristics (link via participants)."""
    return {}
