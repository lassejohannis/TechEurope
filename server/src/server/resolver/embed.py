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
        db.table("entities").update({"inference_embedding": vec}).eq("id", entity_id).execute()
    except Exception as e:
        logger.warning("Failed to update inference embedding for %s: %s", entity_id, e)
