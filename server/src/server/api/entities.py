"""GET /entities/{id} — Entity card with Trust-Score + active Facts."""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from server.auth import Principal, require_scope
from server.db import get_db
from server.models import EntityResponse, FactResponse, EvidenceItem
from server.vfs_paths import segment_from_type, slugify_name

router = APIRouter(prefix="/entities", tags=["entities"])


def _is_single_row_not_found(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST116" in text or "multiple (or no) rows returned" in text


def _build_entity(entity_row: dict, facts: list[dict], trust_row: dict | None) -> EntityResponse:
    fact_responses = []
    for f in facts:
        evidence = []
        if f.get("source_record"):
            sr = f["source_record"]
            evidence.append(EvidenceItem(
                source=sr.get("source_type", "unknown"),
                record_id=str(sr.get("id", "")),
                confidence=f.get("confidence"),
            ))
        fact_responses.append(FactResponse(
            id=str(f["id"]),
            subject_id=str(f["subject_id"]),
            predicate=f["predicate"],
            object_id=str(f["object_id"]) if f.get("object_id") else None,
            object_literal=f.get("object_literal"),
            confidence=float(f.get("confidence", 0)),
            derivation=f.get("derivation", "unknown"),
            extraction_method=f.get("extraction_method"),
            valid_from=f["valid_from"],
            valid_to=f.get("valid_to"),
            recorded_at=f["recorded_at"],
            source_id=str(f["source_id"]),
            status=f.get("status", "active"),
            evidence=evidence,
        ))

    return EntityResponse(
        id=str(entity_row["id"]),
        entity_type=entity_row["entity_type"],
        canonical_name=entity_row["canonical_name"],
        aliases=entity_row.get("aliases") or [],
        attrs=entity_row.get("attrs") or {},
        trust_score=float(trust_row.get("trust_score") or 0) if trust_row else 0.0,
        fact_count=int(trust_row.get("fact_count") or 0) if trust_row else 0,
        source_diversity=int(trust_row.get("source_diversity") or 0) if trust_row else 0,
        facts=fact_responses,
    )


class EntityEditRequest(BaseModel):
    canonical_name: str | None = None
    attrs: dict[str, Any] | None = None
    reason: str | None = None


class EntityLinkRequest(BaseModel):
    predicate: str
    target_entity_type: str
    target_canonical_name: str
    target_attrs: dict[str, Any] | None = None
    confidence: float = 0.9
    reason: str | None = None


_ENTITY_TYPE_ALIASES = {
    "company": "organization",
}


def _canonical_entity_type(entity_type: str) -> str:
    return _ENTITY_TYPE_ALIASES.get(entity_type, entity_type)


def _ensure_entity_type_exists(db, entity_type: str) -> None:
    res = (
        db.table("entity_type_config")
        .select("id")
        .eq("id", entity_type)
        .limit(1)
        .execute()
    )
    if res.data:
        return
    db.table("entity_type_config").upsert(
        {
            "id": entity_type,
            "config": {
                "browse_label": segment_from_type(entity_type).replace("-", " ").title(),
                "hard_id_fields": [],
                "search_attrs": [],
                "auto_created": True,
            },
            "approval_status": "approved",
            "auto_proposed": True,
            "proposal_rationale": "Auto-created from entity link edit flow",
        },
        on_conflict="id",
    ).execute()


def _upsert_target_entity(
    db,
    entity_type: str,
    canonical_name: str,
    attrs: dict[str, Any],
) -> str:
    et = _canonical_entity_type(entity_type)
    _ensure_entity_type_exists(db, et)
    slug = slugify_name(canonical_name)
    target_id = f"{et}:{slug}"
    path = f"/{segment_from_type(et)}/{slug}"

    existing_res = db.table("entities").select("*").eq("id", target_id).limit(1).execute()
    existing = existing_res.data[0] if existing_res.data else None
    if existing:
        merged_attrs = dict(existing.get("attrs") or {})
        merged_attrs.update(attrs or {})
        merged_attrs.setdefault("vfs_path", path)
        aliases = list({*(existing.get("aliases") or []), canonical_name})
        db.table("entities").update({
            "canonical_name": canonical_name,
            "aliases": aliases,
            "attrs": merged_attrs,
        }).eq("id", target_id).execute()
        return target_id

    db.table("entities").insert({
        "id": target_id,
        "entity_type": et,
        "canonical_name": canonical_name,
        "aliases": [canonical_name],
        "attrs": {"vfs_path": path, **(attrs or {})},
        "provenance": [],
        "status": "live",
    }).execute()
    return target_id


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(
    entity_id: str,
    as_of: datetime | None = Query(default=None, description="Time-travel: state at this timestamp"),
    db=Depends(get_db),
):
    try:
        entity_res = db.table("entities").select("*").eq("id", entity_id).single().execute()
    except Exception as exc:
        if _is_single_row_not_found(exc):
            raise HTTPException(status_code=404, detail="Entity not found") from exc
        raise
    if not entity_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity_row = entity_res.data

    facts_q = db.table("facts").select("*, source_records(*)").eq("subject_id", entity_id)
    if as_of:
        facts_q = facts_q.lte("valid_from", as_of.isoformat()).or_(
            f"valid_to.is.null,valid_to.gte.{as_of.isoformat()}"
        )
    else:
        facts_q = facts_q.is_("valid_to", "null")
    facts_res = facts_q.execute()
    facts = facts_res.data or []

    # Flatten joined source_records into each fact dict
    for f in facts:
        sr = f.pop("source_records", None)
        f["source_record"] = sr[0] if isinstance(sr, list) and sr else sr

    try:
        trust_res = db.table("entity_trust").select("*").eq("id", entity_id).single().execute()
        trust_row = trust_res.data
    except Exception as exc:
        if _is_single_row_not_found(exc):
            trust_row = None
        else:
            raise

    return _build_entity(entity_row, facts, trust_row)


@router.post("/{entity_id}/edit")
def edit_entity(
    entity_id: str,
    req: EntityEditRequest,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
):
    entity_res = db.table("entities").select("*").eq("id", entity_id).limit(1).execute()
    if not entity_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity = entity_res.data[0]

    patch: dict[str, Any] = {}
    if req.canonical_name and req.canonical_name.strip():
        old_name = str(entity.get("canonical_name") or "")
        new_name = req.canonical_name.strip()
        aliases = list({*(entity.get("aliases") or []), old_name, new_name})
        patch["canonical_name"] = new_name
        patch["aliases"] = aliases

    if req.attrs is not None:
        current_attrs = dict(entity.get("attrs") or {})
        merged_attrs = dict(current_attrs)
        for key, value in req.attrs.items():
            if value is None:
                merged_attrs.pop(key, None)
            else:
                merged_attrs[key] = value
        patch["attrs"] = merged_attrs

    if not patch:
        return {"entity_id": entity_id, "updated": False}

    db.table("entities").update(patch).eq("id", entity_id).execute()

    now = datetime.now(tz=timezone.utc).isoformat()
    sr_id = str(uuid.uuid4())
    db.table("source_records").insert({
        "id": sr_id,
        "source_type": "human_edit",
        "source_id": f"entity_edit:{entity_id}",
        "event_type": "entity_edit",
        "raw_content": req.reason or f"Entity edit: {entity_id}",
        "timestamp": now,
        "metadata": {
            "edited_by": principal.subject,
            "entity_id": entity_id,
            "updated_fields": sorted(patch.keys()),
        },
    }).execute()

    return {"entity_id": entity_id, "updated": True, "updated_fields": sorted(patch.keys()), "audit_record": sr_id}


@router.post("/{entity_id}/link-entity")
def link_entity(
    entity_id: str,
    req: EntityLinkRequest,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
):
    src_res = db.table("entities").select("id").eq("id", entity_id).limit(1).execute()
    if not src_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")

    target_id = _upsert_target_entity(
        db,
        entity_type=req.target_entity_type.strip(),
        canonical_name=req.target_canonical_name.strip(),
        attrs=req.target_attrs or {},
    )

    now = datetime.now(tz=timezone.utc).isoformat()
    sr_id = str(uuid.uuid4())
    db.table("source_records").insert({
        "id": sr_id,
        "source_type": "human_edit",
        "source_id": f"entity_link:{entity_id}:{target_id}",
        "event_type": "entity_link",
        "raw_content": req.reason or f"Linked {entity_id} -[{req.predicate}]-> {target_id}",
        "timestamp": now,
        "metadata": {
            "edited_by": principal.subject,
            "subject_id": entity_id,
            "target_id": target_id,
            "predicate": req.predicate,
        },
    }).execute()

    fact_id = str(uuid.uuid4())
    db.table("facts").insert({
        "id": fact_id,
        "subject_id": entity_id,
        "predicate": req.predicate,
        "object_id": target_id,
        "object_literal": None,
        "confidence": req.confidence,
        "source_id": sr_id,
        "derivation": "human_edit",
        "valid_from": now,
        "status": "live",
    }).execute()

    return {"fact_id": fact_id, "target_entity_id": target_id, "source_record_id": sr_id, "status": "created"}


@router.get("/{entity_id}/provenance")
def get_entity_provenance(
    entity_id: str,
    db=Depends(get_db),
):
    entity_res = db.table("entities").select("id, entity_type, canonical_name").eq("id", entity_id).limit(1).execute()
    if not entity_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity = entity_res.data[0]

    facts_res = (
        db.table("facts")
        .select("id, source_id, status, predicate, recorded_at")
        .or_(f"subject_id.eq.{entity_id},object_id.eq.{entity_id}")
        .execute()
    )
    facts = facts_res.data or []
    fact_ids = [str(f["id"]) for f in facts if f.get("id")]
    source_ids = sorted({str(f["source_id"]) for f in facts if f.get("source_id")})

    src_rows = []
    if source_ids:
        src_res = (
            db.table("source_records")
            .select("id, source_type, event_type, timestamp, metadata")
            .in_("id", source_ids)
            .execute()
        )
        src_rows = src_res.data or []
    fact_count_by_source: dict[str, int] = {}
    for f in facts:
        sid = str(f.get("source_id") or "")
        if sid:
            fact_count_by_source[sid] = fact_count_by_source.get(sid, 0) + 1
    sources = [{
        "source_id": str(s.get("id")),
        "source_type": s.get("source_type"),
        "event_type": s.get("event_type"),
        "timestamp": s.get("timestamp"),
        "metadata": s.get("metadata") or {},
        "fact_count": fact_count_by_source.get(str(s.get("id")), 0),
    } for s in src_rows]
    sources.sort(key=lambda s: str(s.get("timestamp") or ""), reverse=True)

    edits: list[dict[str, Any]] = []
    if fact_ids:
        fc_res = (
            db.table("fact_changes")
            .select("id, kind, fact_id, old_value, new_value, triggered_by, at")
            .in_("fact_id", fact_ids)
            .order("at", desc=True)
            .limit(200)
            .execute()
        )
        edits = fc_res.data or []

    disputed_facts = sum(1 for f in facts if str(f.get("status")) == "disputed")
    pending_entity_res = (
        db.table("resolutions")
        .select("id")
        .eq("status", "pending")
        .or_(f"entity_id_1.eq.{entity_id},entity_id_2.eq.{entity_id}")
        .execute()
    )
    pending_entity_resolutions = len(pending_entity_res.data or [])

    pending_fact_res = (
        db.table("fact_resolutions")
        .select("id, conflict_facts")
        .eq("status", "pending")
        .limit(5000)
        .execute()
    )
    fact_id_set = set(fact_ids)
    pending_fact_resolutions = 0
    for row in (pending_fact_res.data or []):
        conflicts = set(row.get("conflict_facts") or [])
        if conflicts.intersection(fact_id_set):
            pending_fact_resolutions += 1

    return {
        "entity_id": str(entity["id"]),
        "entity_type": entity.get("entity_type"),
        "canonical_name": entity.get("canonical_name"),
        "sources": sources,
        "edits": edits,
        "conflicts": {
            "disputed_facts": disputed_facts,
            "pending_fact_resolutions": pending_fact_resolutions,
            "pending_entity_resolutions": pending_entity_resolutions,
        },
    }
