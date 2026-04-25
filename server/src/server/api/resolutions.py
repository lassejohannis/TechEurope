"""Conflict-Inbox API.

Two surfaces:
- /api/resolutions          — entity-pair ambiguity inbox (Tier-5 of resolver)
- /api/fact-resolutions     — fact-conflict inbox (auto-detected by trigger
                              when two sources disagree about (subject, predicate))

Both expose: GET (list pending) + POST {id}/decide (human decision).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.db import get_db

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


def _enrich_entity_pair(db, row: dict) -> dict:
    """Attach the two entities' name+type for the UI."""
    ids = [row["entity_id_1"], row["entity_id_2"]]
    e_res = (
        db.table("entities")
        .select("id, entity_type, canonical_name, attrs")
        .in_("id", ids)
        .execute()
    )
    by_id = {e["id"]: e for e in (e_res.data or [])}
    row["entity_1"] = by_id.get(row["entity_id_1"])
    row["entity_2"] = by_id.get(row["entity_id_2"])
    return row


def _enrich_fact_conflict(db, row: dict) -> dict:
    """Attach fact rows + their source_records for display."""
    fact_ids = row.get("conflict_facts") or []
    if not fact_ids:
        row["facts"] = []
        return row
    f_res = (
        db.table("facts")
        .select(
            "id, subject_id, predicate, object_id, object_literal, "
            "confidence, source_id, valid_from, recorded_at, status"
        )
        .in_("id", fact_ids)
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
    for f in facts:
        f["source"] = sr_by_id.get(f.get("source_id"))
    row["facts"] = facts
    return row


# ---------------------------------------------------------------------------
# Entity-Pair Inbox: /api/resolutions
# ---------------------------------------------------------------------------


@router.get("/api/resolutions")
def list_entity_pair_resolutions(
    status: Literal["pending", "merged", "rejected"] = "pending",
    limit: int = 50,
    db = Depends(get_db),
):
    """Return entity-pair pending decisions (Tier-5 ambiguity inbox)."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be 1..500")
    res = (
        db.table("resolutions")
        .select("*")
        .eq("status", status)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = [_enrich_entity_pair(db, r) for r in (res.data or [])]
    return {"items": rows, "total": len(rows)}


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
    limit: int = 50,
    db = Depends(get_db),
):
    """Return fact-conflict pending decisions."""
    if limit < 1 or limit > 500:
        raise HTTPException(400, "limit must be 1..500")
    res = (
        db.table("fact_resolutions")
        .select("*")
        .eq("status", status)
        .order("resolved_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = [_enrich_fact_conflict(db, r) for r in (res.data or [])]
    return {"items": rows, "total": len(rows)}


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
