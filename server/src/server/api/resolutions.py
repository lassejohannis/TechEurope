"""Conflict-Inbox API.

Two surfaces:
- /api/resolutions          — entity-pair ambiguity inbox (Tier-5 of resolver)
- /api/fact-resolutions     — fact-conflict inbox (auto-detected by trigger
                              when two sources disagree about (subject, predicate))

Both expose: GET (list pending) + POST {id}/decide (human decision).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from server.db import get_db
from server.trust import get_source_weight

router = APIRouter(tags=["conflicts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class EntityPairDecisionRequest(BaseModel):
    decision: Literal["pick_one", "merge", "reject"]
    chosen_entity_id: Optional[str] = Field(
        default=None,
        description="Required for pick_one/merge — id of the entity that wins",
    )
    decided_by: str = "human"
    note: Optional[str] = None


class FactDecisionRequest(BaseModel):
    decision: Literal["pick_one", "merge", "both_with_qualifier", "reject_all"]
    chosen_fact_id: Optional[str] = None
    qualifier_added: Optional[dict[str, Any]] = None
    decided_by: str = "human"
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _verification_score_for_fact(fact: dict[str, Any]) -> float:
    """Dynamic verification score (0..1), separate from extraction confidence."""
    extraction = float(fact.get("confidence") or 0.0)
    source_type = str((fact.get("source") or {}).get("source_type") or "unknown")
    source_weight = get_source_weight(source_type)

    # 30-day decay; very old facts keep a floor at 0.70.
    recorded_at = _parse_dt(fact.get("recorded_at"))
    if recorded_at is None:
        recency_factor = 0.85
    else:
        age_days = max(0.0, (datetime.now(tz=timezone.utc) - recorded_at).total_seconds() / 86400.0)
        recency_factor = max(0.70, math.exp(-age_days / 30.0))

    status = str(fact.get("status") or "live")
    status_factor = 0.65 if status == "disputed" else (0.80 if status in {"superseded", "invalidated"} else 1.0)

    # Evidence boost for object ids vs. literals (more stable references).
    object_bonus = 1.0 if fact.get("object_id") else 0.92
    object_id = str(fact.get("object_id") or "")
    if object_id:
        # Replies/forward chains are typically less canonical than the base object.
        lowered = object_id.lower()
        if ":re-" in lowered or ":fwd-" in lowered or ":fw-" in lowered:
            object_bonus *= 0.93

    score = extraction * (0.55 + 0.45 * source_weight) * recency_factor * status_factor * object_bonus
    return max(0.0, min(1.0, score))


def _enrich_entity_pairs(db, rows: list[dict]) -> list[dict]:
    """Attach entity metadata for a list of pair-resolution rows (batch)."""
    if not rows:
        return rows
    ids = {
        rid
        for r in rows
        for rid in (r.get("entity_id_1"), r.get("entity_id_2"))
        if rid
    }
    if not ids:
        return rows
    e_res = (
        db.table("entities")
        .select("id, entity_type, canonical_name, attrs")
        .in_("id", list(ids))
        .execute()
    )
    by_id = {e["id"]: e for e in (e_res.data or [])}
    for row in rows:
        row["entity_1"] = by_id.get(row.get("entity_id_1"))
        row["entity_2"] = by_id.get(row.get("entity_id_2"))
    return rows


def _enrich_fact_conflicts(db, rows: list[dict]) -> list[dict]:
    """Attach fact rows + source_records for list of fact-resolution rows (batch)."""
    if not rows:
        return rows
    all_fact_ids: set[str] = {
        fid
        for row in rows
        for fid in (row.get("conflict_facts") or [])
        if fid
    }
    if not all_fact_ids:
        for row in rows:
            row["facts"] = []
        return rows
    f_res = (
        db.table("facts")
        .select(
            "id, subject_id, predicate, object_id, object_literal, "
            "confidence, source_id, valid_from, recorded_at, status"
        )
        .in_("id", list(all_fact_ids))
        .execute()
    )
    facts = f_res.data or []
    src_ids = list({f["source_id"] for f in facts if f.get("source_id")})
    sr_res = (
        db.table("source_records")
        .select("id, source_type, source_uri")
        .in_("id", src_ids)
        .execute()
        if src_ids
        else None
    )
    sr_by_id = {s["id"]: s for s in (sr_res.data or [])} if sr_res else {}
    facts_by_id: dict[str, dict] = {}
    for f in facts:
        f["source"] = sr_by_id.get(f.get("source_id"))
        f["extraction_confidence"] = float(f.get("confidence") or 0.0)
        f["verification_score"] = _verification_score_for_fact(f)
        facts_by_id[f["id"]] = f
    for row in rows:
        row_fact_ids = row.get("conflict_facts") or []
        row["facts"] = [facts_by_id[fid] for fid in row_fact_ids if fid in facts_by_id]
    return rows


# ---------------------------------------------------------------------------
# Entity-Pair Inbox: /api/resolutions
# ---------------------------------------------------------------------------


@router.get("/api/resolutions")
def list_entity_pair_resolutions(
    status: Literal["pending", "merged", "rejected"] = "pending",
    limit: int | None = Query(default=None, ge=1, le=5000),
    db = Depends(get_db),
):
    """Return entity-pair pending decisions (Tier-5 ambiguity inbox)."""
    total_res = (
        db.table("resolutions")
        .select("id", count="exact", head=True)
        .eq("status", status)
        .execute()
    )
    total = int(total_res.count or 0)

    query = (
        db.table("resolutions")
        .select("*")
        .eq("status", status)
        .order("created_at", desc=True)
    )
    if limit is not None:
        query = query.limit(limit)
    res = query.execute()
    rows = _enrich_entity_pairs(db, list(res.data or []))
    return {"items": rows, "total": total}


@router.post("/api/resolutions/{resolution_id}/decide")
def decide_entity_pair(
    resolution_id: str,
    body: EntityPairDecisionRequest,
    db = Depends(get_db),
):
    """Apply a human decision on an entity-pair resolution."""
    res = (
        db.table("resolutions").select("*").eq("id", resolution_id).single().execute()
    )
    row = res.data
    if not row:
        raise HTTPException(404, "resolution not found")
    if row["status"] != "pending":
        raise HTTPException(409, f"already decided (status={row['status']})")

    e1, e2 = row["entity_id_1"], row["entity_id_2"]

    if body.decision == "merge":
        # Pick one as winner, append the other's aliases + provenance to it,
        # then DELETE the loser. cascading FK on facts.subject/object_id moves
        # references via the new entity_id we keep — for now we just mark
        # "merged" in the resolutions row; full merge-of-aliases is a follow-up.
        winner_id = body.chosen_entity_id or e1
        loser_id = e2 if winner_id == e1 else e1
        new_status = "merged"
        # Move loser's aliases into winner
        loser = db.table("entities").select("aliases").eq("id", loser_id).single().execute().data
        winner = db.table("entities").select("aliases").eq("id", winner_id).single().execute().data
        merged_aliases = list({*(winner.get("aliases") or []), *(loser.get("aliases") or [])})
        db.table("entities").update({"aliases": merged_aliases}).eq("id", winner_id).execute()
    elif body.decision == "pick_one":
        # No automatic merge; just record the pick + close the inbox row.
        winner_id = body.chosen_entity_id or e1
        new_status = "merged"
    else:  # reject
        winner_id = None
        new_status = "rejected"

    db.table("resolutions").update(
        {
            "status": new_status,
            "decided_at": _now_iso(),
            "decided_by": body.decided_by,
            "resolution_signals": {
                **(row.get("resolution_signals") or {}),
                "decision": body.decision,
                "winner_id": winner_id,
                "note": body.note,
            },
        }
    ).eq("id", resolution_id).execute()

    return {"status": new_status, "winner_id": winner_id}


# ---------------------------------------------------------------------------
# Fact-Conflict Inbox: /api/fact-resolutions
# ---------------------------------------------------------------------------


@router.get("/api/fact-resolutions")
def list_fact_resolutions(
    status: Literal["pending", "auto_resolved", "human_resolved", "rejected"] = "pending",
    limit: int | None = Query(default=None, ge=1, le=5000),
    db = Depends(get_db),
):
    """Return fact-conflict pending decisions."""
    total_res = (
        db.table("fact_resolutions")
        .select("id", count="exact", head=True)
        .eq("status", status)
        .execute()
    )
    total = int(total_res.count or 0)

    query = (
        db.table("fact_resolutions")
        .select("*")
        .eq("status", status)
        .order("resolved_at", desc=True)
    )
    if limit is not None:
        query = query.limit(limit)
    res = query.execute()
    rows = _enrich_fact_conflicts(db, list(res.data or []))
    return {"items": rows, "total": total}


@router.post("/api/fact-resolutions/{resolution_id}/decide")
def decide_fact_conflict(
    resolution_id: str,
    body: FactDecisionRequest,
    db = Depends(get_db),
):
    """Apply a human decision on a fact-conflict resolution.

    pick_one: chosen_fact_id becomes 'live', rest become 'superseded'.
    reject_all: all conflict facts become 'rejected'.
    both_with_qualifier: both stay 'live', resolution_signals records qualifier.
    """
    res = (
        db.table("fact_resolutions").select("*").eq("id", resolution_id).single().execute()
    )
    row = res.data
    if not row:
        raise HTTPException(404, "resolution not found")
    if row["status"] != "pending":
        raise HTTPException(409, f"already decided (status={row['status']})")

    fact_ids = row.get("conflict_facts") or []
    now = _now_iso()

    if body.decision == "pick_one":
        winner_id = body.chosen_fact_id
        if not winner_id or winner_id not in fact_ids:
            raise HTTPException(400, "chosen_fact_id must be one of conflict_facts")
        db.table("facts").update({"status": "live"}).eq("id", winner_id).execute()
        for fid in fact_ids:
            if fid == winner_id:
                continue
            db.table("facts").update(
                {"status": "superseded", "valid_to": now, "superseded_by": winner_id}
            ).eq("id", fid).execute()
        chosen = winner_id
    elif body.decision == "reject_all":
        for fid in fact_ids:
            db.table("facts").update(
                {"status": "superseded", "valid_to": now}
            ).eq("id", fid).execute()
        chosen = None
    elif body.decision == "both_with_qualifier":
        # Leave both live; UI is responsible for follow-up qualifier facts.
        chosen = None
    else:
        chosen = None

    db.table("fact_resolutions").update(
        {
            "status": "human_resolved",
            "decision": body.decision,
            "chosen_fact_id": chosen,
            "qualifier_added": body.qualifier_added,
            "rationale": body.note or row.get("rationale"),
            "resolved_at": now,
            "resolved_by": body.decided_by,
        }
    ).eq("id", resolution_id).execute()

    return {"status": "human_resolved", "chosen_fact_id": chosen}


# ---------------------------------------------------------------------------
# Trust-weights (read-only) — used by Trust-Weight-Editor in the frontend
# ---------------------------------------------------------------------------


@router.get("/api/trust-weights")
def list_trust_weights():
    """Return source_type → trust_weight from config/source_trust_weights.yaml."""
    from server.trust import _load_weights

    return {"weights": _load_weights()}
