"""Admin endpoints (reload ontologies, GDPR delete, reingest, pending types, Neo4j replay)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from server.auth import Principal, require_scope
from server.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


class ReingestRequest(BaseModel):
    source_record_ids: list[str] = Field(..., min_length=1)
    reason: str | None = None


class PendingTypeDecision(BaseModel):
    kind: str = Field(..., pattern="^(entity|edge|source_mapping)$")
    decision: str = Field(..., pattern="^(approved|rejected)$")
    note: str | None = None


class RefreshBrowseRequest(BaseModel):
    limit: int = Field(default=250, ge=1, le=2000)
    infer_mappings: bool = True
    auto_approve_mappings: bool = True
    llm_extract: bool = False


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


@router.post("/refresh-browse-tree", status_code=200)
def refresh_browse_tree(
    req: RefreshBrowseRequest = Body(default=RefreshBrowseRequest()),
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
) -> dict[str, Any]:
    """Run a compact ontology+resolver refresh so Browse shows newly inferable entities.

    Intended for dev/demo UX: frontend can trigger this on reload, then fetch
    `/api/vfs/*` again to reflect newly created entities.
    """
    from server.cli import (
        _canonical_entity_type,
        _persist_entity,
        _persist_fact,
        _persist_relationship_fact,
    )
    from server.resolver.cascade import CandidateEntity
    from server.ontology.engine import apply_mapping
    from server.ontology.propose import infer_source_mapping, persist_proposal, validate_proposal
    from server.resolver.cascade import resolve as cascade_resolve
    from server.resolver.cascade import write_pending_inbox
    from server.resolver.extract import extract_candidates

    records_res = (
        db.table("source_records")
        .select("id, source_type, payload")
        .order("ingested_at", desc=True)
        .limit(req.limit)
        .execute()
    )
    records = records_res.data or []
    if not records:
        return {
            "processed_records": 0,
            "entities_created": 0,
            "entities_merged": 0,
            "entities_inboxed": 0,
            "facts_created": 0,
            "relationship_hints": 0,
            "mappings_inferred": 0,
            "mappings_auto_approved": 0,
            "triggered_by": principal.subject,
        }

    mapping_cache: dict[str, dict | None] = {}

    def _mapping_for(source_type: str) -> dict | None:
        if source_type in mapping_cache:
            return mapping_cache[source_type]
        row_res = (
            db.table("source_type_mapping")
            .select("config, status")
            .eq("source_type", source_type)
            .limit(1)
            .execute()
        )
        row = (row_res.data or [None])[0]
        cfg = (row.get("config") or {}) if row and row.get("status") == "approved" else None
        mapping_cache[source_type] = cfg
        return cfg

    inferred = 0
    auto_approved = 0
    if req.infer_mappings:
        for stype in sorted({str(r.get("source_type") or "") for r in records if r.get("source_type")}):
            if _mapping_for(stype) is not None:
                continue
            sample_res = (
                db.table("source_records")
                .select("id, source_type, payload")
                .eq("source_type", stype)
                .limit(8)
                .execute()
            )
            sample_records = sample_res.data or []
            if len(sample_records) < 2:
                continue

            proposal = infer_source_mapping(stype, sample_records[:5], db)
            if proposal is None:
                continue
            validation = validate_proposal(proposal, sample_records[5:] or sample_records[:1])
            status = persist_proposal(
                proposal,
                db,
                sample_ids=[r["id"] for r in sample_records[:5]],
                validation_stats=validation,
                auto_approve=req.auto_approve_mappings,
            )
            inferred += 1
            if status == "approved":
                auto_approved += 1
                mapping_cache[stype] = proposal.model_dump()

    stats = {
        "processed_records": 0,
        "entities_created": 0,
        "entities_merged": 0,
        "entities_inboxed": 0,
        "facts_created": 0,
        "relationship_hints": 0,
        "record_errors": 0,
    }

    def _fallback_document_candidate(rec: dict[str, Any]) -> list[CandidateEntity]:
        payload = rec.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        source_type = str(rec.get("source_type") or "document")
        # Auto-create a generic document entity for previously unseen source shapes.
        title = (
            payload.get("title")
            or payload.get("subject")
            or payload.get("document_title")
            or payload.get("filename")
            or payload.get("file_name")
            or payload.get("name")
        )
        canonical_name = str(title).strip() if title else ""
        if not canonical_name:
            rid = str(rec.get("id") or "")
            canonical_name = f"{source_type.replace('_', ' ').title()} {rid[:8] or 'Document'}"
        attrs = {
            "document_type": source_type,
            "source_record_id": str(rec.get("id") or ""),
        }
        for key in ("mime_type", "file_type", "path", "uri", "author", "created_at"):
            if payload.get(key) is not None:
                attrs[key] = payload.get(key)
        return [CandidateEntity(entity_type="document", canonical_name=canonical_name, attrs=attrs, source_id=str(rec.get("id") or ""))]

    for rec in records:
        try:
            stats["processed_records"] += 1
            source_type = str(rec.get("source_type") or "")
            cfg = _mapping_for(source_type) if source_type else None
            if cfg is not None:
                candidates, pending_facts = apply_mapping(rec, cfg)
            else:
                candidates, pending_facts = extract_candidates(rec, llm_extract=req.llm_extract)
                if not candidates and not pending_facts:
                    candidates = _fallback_document_candidate(rec)

            if not candidates and not pending_facts:
                continue

            name_to_id: dict[tuple[str, str], str] = {}
            for cand in candidates:
                result = cascade_resolve(cand, db)
                if result.action == "inbox":
                    entity_id = _persist_entity(db, cand, None)
                    if not entity_id:
                        continue
                    canonical_type = _canonical_entity_type(cand.entity_type)
                    name_to_id[(canonical_type, cand.canonical_name)] = entity_id
                    write_pending_inbox(cand, result, db)
                    stats["entities_inboxed"] += 1
                else:
                    same_type_match = result.matched_id if result.tier in (
                        "hard_id", "alias", "embedding", "pioneer"
                    ) else None
                    entity_id = _persist_entity(db, cand, same_type_match)
                    if not entity_id:
                        continue
                    canonical_type = _canonical_entity_type(cand.entity_type)
                    name_to_id[(canonical_type, cand.canonical_name)] = entity_id
                    if same_type_match:
                        stats["entities_merged"] += 1
                    else:
                        stats["entities_created"] += 1

                if result.relationship_hint:
                    predicate, _target_type, target_id = result.relationship_hint
                    if _persist_relationship_fact(
                        db, entity_id, predicate, target_id, rec["id"], result.confidence
                    ):
                        stats["relationship_hints"] += 1

            for pf in pending_facts:
                if _persist_fact(db, pf, name_to_id, rec["id"]):
                    stats["facts_created"] += 1
        except Exception as exc:
            stats["record_errors"] += 1
            logger.exception(
                "refresh-browse-tree failed for source_record=%s source_type=%s: %s",
                rec.get("id"),
                rec.get("source_type"),
                exc,
            )

    summary = {
        **stats,
        "mappings_inferred": inferred,
        "mappings_auto_approved": auto_approved,
        "triggered_by": principal.subject,
    }
    logger.info("refresh-browse-tree done: %s", summary)
    return summary


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
    body: PendingTypeDecision,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("admin")),
) -> dict[str, Any]:
    """Approve/reject a pending row. `kind` selects which table to update."""
    kind = body.kind
    decision = body

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
