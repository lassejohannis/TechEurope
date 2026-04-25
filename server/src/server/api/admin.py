"""Admin endpoints (reload ontologies, GDPR delete, reingest, pending types, Neo4j replay)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from server.auth import Principal, require_scope
from server.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


class ReingestRequest(BaseModel):
    source_record_ids: list[str] = Field(..., min_length=1)
    reason: str | None = None


class PendingTypeDecision(BaseModel):
    decision: str = Field(..., pattern="^(approved|rejected)$")
    note: str | None = None


@router.post("/reload-ontologies", status_code=200)
def reload_ontologies(
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
):
    """Reload YAML ontologies from config/ontologies/ into entity_type_config / edge_type_config."""
    try:
        from server.ontology.loader import load_ontologies  # type: ignore  (WS-0 delivers this)
        from server.vfs_paths import get_type_slug_maps
        loaded = load_ontologies(db)
        get_type_slug_maps.cache_clear()
        return {"status": "ok", "loaded": loaded}
    except ImportError:
        return {"status": "stub", "message": "Ontology loader not yet available (WS-0 pending)"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/source-records/{source_record_id}", status_code=200)
def gdpr_delete_source(
    source_record_id: str,
    confirm: bool = False,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
):
    """GDPR Source-Delete Cascade: deletes source record + cascades to derived facts.

    Requires ?confirm=true to prevent accidental deletion.
    ON DELETE CASCADE on facts.source_id handles the cascade at DB level (WS-0 migration).
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=true to execute GDPR deletion. This is irreversible.",
        )

    sr_res = db.table("source_records").select("id, source_type").eq(
        "id", source_record_id
    ).limit(1).execute()
    if not (sr_res.data or []):
        raise HTTPException(status_code=404, detail="Source record not found")

    # Count facts that will cascade
    facts_count_res = db.table("facts").select("id", count="exact").eq(
        "source_id", source_record_id
    ).execute()
    facts_count = facts_count_res.count or 0

    db.table("source_records").delete().eq("id", source_record_id).execute()

    return {
        "deleted_source_record": source_record_id,
        "cascaded_facts": facts_count,
        "gdpr_compliant": True,
    }


@router.post("/reingest", status_code=200)
def reingest_sources(
    req: ReingestRequest = Body(...),
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
) -> dict[str, Any]:
    """Mark facts derived from given source_records as needs_refresh.

    Re-derivation is lazy (no cron) — the resolver/extractor pipeline picks
    these up on next run. Reuses the `mark_facts_needs_refresh` RPC defined
    in 001_init.sql.
    """
    # Validate IDs exist (avoid silent no-ops)
    res = db.table("source_records").select("id").in_("id", req.source_record_ids).execute()
    found = {r["id"] for r in (res.data or [])}
    missing = sorted(set(req.source_record_ids) - found)

    affected = 0
    try:
        rpc_res = db.rpc("mark_facts_needs_refresh", {"updated_source_ids": list(found)}).execute()
        affected = int(rpc_res.data or 0)
    except Exception:  # RPC missing in some envs — fall back to direct update
        update_res = (
            db.table("facts")
            .update({"status": "needs_refresh"})
            .in_("source_id", list(found))
            .neq("status", "needs_refresh")
            .execute()
        )
        affected = len(update_res.data or [])

    return {
        "queued_for_refresh": affected,
        "missing_source_records": missing,
        "triggered_by": principal.subject,
    }


@router.get("/pending-types", status_code=200)
def list_pending_types(
    kind: str | None = None,
    limit: int = 50,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
) -> dict[str, Any]:
    """Unified inbox over the 3 places where 'pending' lives:

    - entity_type_config WHERE approval_status='pending' (auto-proposed types)
    - edge_type_config   WHERE approval_status='pending' (auto-proposed predicates)
    - source_type_mapping WHERE status='pending'         (AI-inferred extractors)

    `kind` filter values: "entity" | "edge" | "source_mapping" | None (all).
    """
    items: list[dict[str, Any]] = []

    if kind in (None, "entity"):
        res = (
            db.table("entity_type_config")
            .select("id, config, approval_status, auto_proposed, proposed_by_source_id, "
                    "similarity_to_nearest, proposal_rationale")
            .eq("approval_status", "pending")
            .limit(limit)
            .execute()
        )
        for r in res.data or []:
            items.append({**r, "kind": "entity"})

    if kind in (None, "edge"):
        res = (
            db.table("edge_type_config")
            .select("id, config, approval_status, auto_proposed, proposed_by_source_id, "
                    "similarity_to_nearest, proposal_rationale, from_type, to_type")
            .eq("approval_status", "pending")
            .limit(limit)
            .execute()
        )
        for r in res.data or []:
            items.append({**r, "kind": "edge"})

    if kind in (None, "source_mapping"):
        res = (
            db.table("source_type_mapping")
            .select("id, source_type, mapping_version, config, status, validation_stats, "
                    "rationale, created_from_sample_ids, proposed_at")
            .eq("status", "pending")
            .limit(limit)
            .execute()
        )
        for r in res.data or []:
            items.append({**r, "kind": "source_mapping"})

    return {"items": items, "total": len(items), "kind_filter": kind}


@router.post("/pending-types/{pending_id}/decide", status_code=200)
def decide_pending_type(
    pending_id: str,
    decision: PendingTypeDecision,
    kind: str = Body(..., embed=True),  # "entity" | "edge" | "source_mapping"
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
) -> dict[str, Any]:
    """Approve/reject a pending row. `kind` selects which table to update."""
    if kind not in ("entity", "edge", "source_mapping"):
        raise HTTPException(status_code=400, detail="kind must be entity|edge|source_mapping")

    table = {
        "entity": "entity_type_config",
        "edge": "edge_type_config",
        "source_mapping": "source_type_mapping",
    }[kind]
    status_col = "status" if kind == "source_mapping" else "approval_status"

    res = db.table(table).select("*").eq("id", pending_id).single().execute()
    row = res.data
    if not row:
        raise HTTPException(status_code=404, detail=f"{kind} {pending_id!r} not found")
    if row.get(status_col) != "pending":
        raise HTTPException(status_code=409, detail=f"already {row.get(status_col)}")

    now = datetime.now(tz=timezone.utc).isoformat()
    update: dict[str, Any] = {
        status_col: decision.decision,
    }
    if kind != "source_mapping":
        update["approved_at"] = now
        update["approved_by"] = principal.subject
    else:
        update["approved_at"] = now
        update["approved_by"] = principal.subject

    db.table(table).update(update).eq("id", pending_id).execute()

    return {
        "id": pending_id,
        "kind": kind,
        "decision": decision.decision,
        "decided_by": principal.subject,
    }


# ---------------------------------------------------------------------------
# Neo4j projection control (from origin/main — kept under /admin scope)
# ---------------------------------------------------------------------------


@router.post("/projection/replay", status_code=202)
async def trigger_projection_replay(
    request: Request,
    background_tasks: BackgroundTasks,
    principal: Principal = Depends(require_scope("admin")),
):
    """Trigger a full Postgres → Neo4j replay in the background.

    Returns 202 immediately; the replay runs asynchronously and can take
    30–120 seconds depending on data volume.
    """
    proj = getattr(request.app.state, "projection", None)
    if proj is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j projection not active — running Postgres-only mode.",
        )
    background_tasks.add_task(proj.replay_all)
    return {"status": "replay_started", "message": "Full replay running in background."}


@router.get("/projection/health", status_code=200)
async def projection_health(
    request: Request,
    principal: Principal = Depends(require_scope("read")),
):
    """Return Neo4j projection health + sync stats."""
    proj = getattr(request.app.state, "projection", None)
    if proj is None:
        return {"status": "down", "reason": "neo4j not configured"}
    return await proj.healthcheck()
