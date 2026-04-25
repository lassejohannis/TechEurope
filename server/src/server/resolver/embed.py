"""Embedding layer for entity resolution — Tier A (name) and Tier B (inference)."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HOT_ENTITY_FACT_THRESHOLD = 5


def build_embedding_text(canonical_name: str, attrs: dict[str, Any]) -> str:
    parts = [canonical_name]
    for key in ("industry", "category", "email", "domain", "product_name", "description"):
        if val := attrs.get(key):
            parts.append(str(val))
    return " | ".join(parts)


def get_name_embedding(text: str) -> list[float] | None:
    try:
        from server.db import embed_text
        return embed_text(text)
    except Exception as e:
        logger.warning("Embedding unavailable: %s", e)
        return None


def is_hot_entity(entity_id: str, db: Any) -> bool:
    try:
        res = (
            db.table("facts")
            .select("id", count="exact")
            .eq("subject_id", entity_id)
            .is_("valid_to", "null")
            .execute()
        )
        return (res.count or 0) >= HOT_ENTITY_FACT_THRESHOLD
    except Exception:
        return False


def refresh_inference_embedding(entity_id: str, text: str, db: Any) -> None:
    """Compute and persist Tier-B inference embedding for a hot entity."""
    vec = get_name_embedding(text)
    if vec is None:
        return
    try:
        db.table("entities").update(
            {"inference_embedding": vec, "inference_needs_refresh": False}
        ).eq("id", entity_id).execute()
    except Exception as e:
        logger.warning("Failed to update inference embedding for %s: %s", entity_id, e)


def build_inference_text(entity_id: str, db: Any, max_facts: int = 30) -> str:
    """Build a context-rich text from an entity's facts for Tier-B embedding.

    Format: "<canonical_name> (<entity_type>). predicate1: target1. predicate2: target2."
    Capped to keep token budget under control.
    """
    e_res = db.table("entities").select(
        "id, entity_type, canonical_name"
    ).eq("id", entity_id).single().execute()
    e = e_res.data or {}
    parts = [f"{e.get('canonical_name', '')} ({e.get('entity_type', '')})."]

    facts_res = (
        db.table("facts")
        .select("predicate, object_id, object_literal")
        .eq("subject_id", entity_id)
        .is_("valid_to", "null")
        .limit(max_facts)
        .execute()
    )
    for f in facts_res.data or []:
        target = f.get("object_id") or f.get("object_literal")
        if isinstance(target, dict):
            target = target.get("name") or target.get("quote") or str(target)
        if target:
            parts.append(f"{f['predicate']}: {target}")
    return " ".join(parts)
