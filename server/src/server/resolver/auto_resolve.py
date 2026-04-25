"""Auto-resolution cascade for disputed facts.

Pipeline:
1. Read pending fact_resolutions rows.
2. For each row, fetch the conflicting facts.
3. Walk the 4-tier cascade:
   T1 Cross-Confirmation: fact with ≥ N independent sources beats single-source.
   T2 Authority: higher source_trust_weight wins (config/source_trust_weights.yaml).
   T3 Confidence: higher confidence wins.
   T4 Recency: newer valid_from wins (last-resort tiebreaker).
4. Clear winner: supersede loser (valid_to=now, status='superseded',
   superseded_by=winner.id), promote winner back to 'live', mark
   fact_resolutions.status='auto_resolved' with chosen_fact_id.
5. No clear winner: leave for human inbox (status='pending').

Idempotent — safe to re-run; rows already resolved are skipped.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from server.trust import authority_score

logger = logging.getLogger(__name__)

CROSS_CONFIRM_MIN_SOURCES = 2  # Tier-1 trigger: >= this many distinct sources
CONFIDENCE_DELTA_TIE = 0.05  # confidence diff < this is a tie (defer to next tier)


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _fetch_pending(db: Any, limit: int) -> list[dict[str, Any]]:
    res = (
        db.table("fact_resolutions")
        .select("id, conflict_facts, status, rationale")
        .eq("status", "pending")
        .limit(limit)
        .execute()
    )
    return res.data or []


def _fetch_facts(db: Any, fact_ids: list[str]) -> list[dict[str, Any]]:
    res = (
        db.table("facts")
        .select(
            "id, subject_id, predicate, object_id, object_literal, "
            "confidence, source_id, valid_from, recorded_at, status"
        )
        .in_("id", fact_ids)
        .execute()
    )
    return res.data or []


def _source_type_for(db: Any, source_id: str) -> str:
    """Look up source_records.source_type for a fact's source_id."""
    if not source_id:
        return ""
    res = (
        db.table("source_records")
        .select("source_type")
        .eq("id", source_id)
        .single()
        .execute()
    )
    return ((res.data or {}).get("source_type")) or ""


def _cross_confirmation(facts: list[dict], db: Any) -> dict | None:
    """Tier 1: fact with ≥ N independent source_ids beats the rest."""
    grouped: dict[tuple, list[dict]] = {}
    for f in facts:
        key = (f.get("object_id") or "", str(f.get("object_literal") or ""))
        grouped.setdefault(key, []).append(f)

    for value_key, group in grouped.items():
        sources = {f.get("source_id") for f in group if f.get("source_id")}
        if len(sources) >= CROSS_CONFIRM_MIN_SOURCES:
            # Pick representative fact = highest confidence
            best = max(group, key=lambda x: float(x.get("confidence") or 0))
            best["_signal"] = f"cross_confirmation:{len(sources)} sources"
            return best
    return None


def _authority(facts: list[dict], db: Any) -> dict | None:
    """Tier 2: highest source_trust_weight × confidence."""
    scored: list[tuple[float, dict]] = []
    for f in facts:
        source_type = _source_type_for(db, f.get("source_id") or "")
        score = authority_score(float(f.get("confidence") or 0), source_type)
        scored.append((score, f))

    if not scored:
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    top, top_score = scored[0][1], scored[0][0]
    runner_up_score = scored[1][0] if len(scored) > 1 else 0.0
    if top_score - runner_up_score > CONFIDENCE_DELTA_TIE:
        top["_signal"] = f"authority:{top_score:.2f} vs {runner_up_score:.2f}"
        return top
    return None


def _confidence(facts: list[dict]) -> dict | None:
    """Tier 3: pure highest confidence wins (must beat runner-up by > delta)."""
    scored = sorted(facts, key=lambda x: float(x.get("confidence") or 0), reverse=True)
    if len(scored) < 2:
        return scored[0] if scored else None
    top, runner_up = scored[0], scored[1]
    if float(top["confidence"]) - float(runner_up["confidence"]) > CONFIDENCE_DELTA_TIE:
        top["_signal"] = (
            f"confidence:{float(top['confidence']):.2f} vs "
            f"{float(runner_up['confidence']):.2f}"
        )
        return top
    return None


def _recency(facts: list[dict]) -> dict | None:
    """Tier 4: newest recorded_at wins (last-resort tiebreaker)."""
    if not facts:
        return None
    scored = sorted(facts, key=lambda x: x.get("recorded_at") or "", reverse=True)
    top = scored[0]
    top["_signal"] = f"recency:{top.get('recorded_at')}"
    return top


def _supersede_loser(db: Any, winner: dict, losers: list[dict]) -> None:
    """Mark losers superseded, promote winner back to 'live'."""
    now = _now_iso()
    db.table("facts").update(
        {"status": "live"}
    ).eq("id", winner["id"]).execute()

    for loser in losers:
        if loser["id"] == winner["id"]:
            continue
        db.table("facts").update(
            {
                "status": "superseded",
                "valid_to": now,
                "superseded_by": winner["id"],
            }
        ).eq("id", loser["id"]).execute()


def _close_resolution(
    db: Any, resolution_id: str, winner: dict, signal: str
) -> None:
    db.table("fact_resolutions").update(
        {
            "status": "auto_resolved",
            "chosen_fact_id": winner["id"],
            "decision": "pick_one",
            "rationale": signal,
            "resolved_at": _now_iso(),
            "resolved_by": "auto_cascade",
        }
    ).eq("id", resolution_id).execute()


def auto_resolve_disputed_facts(db: Any, limit: int = 200) -> dict[str, int]:
    """Walk pending fact_resolutions and apply the cascade. Returns stats."""
    stats = {"checked": 0, "auto_resolved": 0, "left_pending": 0, "skipped": 0}

    pending = _fetch_pending(db, limit)
    stats["checked"] = len(pending)

    for resolution in pending:
        fact_ids = resolution.get("conflict_facts") or []
        if not fact_ids:
            stats["skipped"] += 1
            continue

        facts = _fetch_facts(db, fact_ids)
        if len(facts) < 2:
            stats["skipped"] += 1
            continue

        winner: dict | None = None
        for tier in (_cross_confirmation, _authority, _confidence, _recency):
            try:
                if tier is _cross_confirmation:
                    winner = tier(facts, db)
                elif tier is _authority:
                    winner = tier(facts, db)
                else:
                    winner = tier(facts)
                if winner:
                    break
            except Exception as exc:
                logger.warning("Tier %s errored: %s", tier.__name__, exc)
                continue

        if not winner:
            stats["left_pending"] += 1
            continue

        signal = winner.get("_signal", "auto-resolved")
        try:
            _supersede_loser(db, winner, facts)
            _close_resolution(db, resolution["id"], winner, signal)
            stats["auto_resolved"] += 1
        except Exception as exc:
            logger.warning("supersede failed for resolution %s: %s", resolution["id"], exc)
            stats["skipped"] += 1

    return stats
