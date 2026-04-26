"""VFS endpoints: List/Read/Write/Delete nodes via path-based addressing.

Path → Entity type mapping:
  /companies                           → list Company entities
  /companies/{slug}                    → Company entity detail
  /companies/{slug}/contacts           → Person entities linked via works_at
  /companies/{slug}/deals              → Deal entities linked to company
  /companies/{slug}/deals/{slug}/...   → nested node traversal
  /persons/{slug}                      → Person entity (direct lookup)
  /documents/{slug}                    → Document entity
  /communications/{slug}               → Communication entity

Nodes also store attrs.vfs_path for direct path lookup.
"""

from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import get_db
from server.models import (
    ProposeFactRequest,
    ProposeFactResponse,
    VfsListResponse,
    VfsNode,
    VfsPatchRequest,
    VfsPatchResponse,
)
from server.vfs_paths import (
    glob_to_ilike,
    pluralize_entity_type,
    segment_from_type,
    type_from_segment,
)

router = APIRouter(prefix="/vfs", tags=["vfs"])
logger = logging.getLogger(__name__)

_COLLECTION_ALIASES: dict[str, str] = {
    "contacts": "person",
}


def _titleize_slug(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").title()


def _missing_column(exc: Exception, column: str) -> bool:
    text = str(exc).lower()
    return column.lower() in text and (
        "column" in text
        or "schema cache" in text
        or "pgrst" in text
    )


def _list_active_entities(db, *, entity_type: str | None = None, limit: int = 500, glob: str | None = None):
    """Schema-compatible active-entity listing.

    Prefers `deleted_at is null` (new soft-delete schema); falls back to
    `status != archived` when `deleted_at` doesn't exist yet.
    """
    def _build_base():
        q = db.table("entities").select("*")
        if entity_type:
            q = q.eq("entity_type", entity_type)
        if glob:
            q = q.ilike("attrs->>vfs_path", glob_to_ilike(glob))
        return q

    try:
        return _build_base().is_("deleted_at", "null").limit(limit).execute()
    except Exception as exc:
        if not _missing_column(exc, "deleted_at"):
            raise
        logger.warning("entities.deleted_at missing; falling back to status filter in vfs list")
        return _build_base().neq("status", "archived").limit(limit).execute()


def _count_active_entities(db, *, entity_type: str) -> int:
    """Count active entities per type with schema-compatible filters."""
    def _build_base():
        return db.table("entities").select("id", count="exact", head=True).eq("entity_type", entity_type)

    try:
        res = _build_base().is_("deleted_at", "null").execute()
    except Exception as exc:
        if not _missing_column(exc, "deleted_at"):
            raise
        logger.warning("entities.deleted_at missing; falling back to status filter in vfs count")
        res = _build_base().neq("status", "archived").execute()
    return int(res.count or 0)


def _get_active_entity_for_patch(db, *, slug: str, entity_type: str):
    try:
        uuid.UUID(slug)
        try:
            return (
                db.table("entities")
                .select("id, attrs")
                .eq("id", slug)
                .is_("deleted_at", "null")
                .single()
                .execute()
            )
        except Exception as exc:
            if not _missing_column(exc, "deleted_at"):
                raise
            logger.warning("entities.deleted_at missing; falling back to status filter in vfs patch lookup (id)")
            return (
                db.table("entities")
                .select("id, attrs")
                .eq("id", slug)
                .neq("status", "archived")
                .single()
                .execute()
            )
    except ValueError:
        def _name_base():
            return (
                db.table("entities")
                .select("id, attrs")
                .eq("entity_type", entity_type)
                .ilike("canonical_name", f"%{slug.replace('-', ' ')}%")
            )

        try:
            return (
                _name_base().is_("deleted_at", "null").limit(1).execute()
            )
        except Exception as exc:
            if not _missing_column(exc, "deleted_at"):
                raise
            logger.warning("entities.deleted_at missing; falling back to status filter in vfs patch lookup (name)")
            return (
                _name_base().neq("status", "archived").limit(1).execute()
            )

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def _entity_to_vfs_node(e: dict, path: str) -> VfsNode:
    attrs = e.get("attrs") or {}
    fallback_path = path
    if not fallback_path:
        seg = pluralize_entity_type(str(e.get("entity_type", "entity")))
        fallback_path = f"/{seg}/{e.get('id')}"
    return VfsNode(
        path=attrs.get("vfs_path", fallback_path),
        type=e["entity_type"],
        entity_id=str(e["id"]),
        content={
            "canonical_name": e["canonical_name"],
            "aliases": e.get("aliases") or [],
            **attrs,
        },
        metadata={
            "entity_type": e["entity_type"],
            "id": str(e["id"]),
        },
        created_at=e.get("created_at"),
        updated_at=e.get("updated_at"),
    )


def _path_segments(path: str) -> list[str]:
    return [s for s in path.strip("/").split("/") if s]


# ---------------------------------------------------------------------------
# GET /vfs/_sections — dynamic browse sections from ontology config
# ---------------------------------------------------------------------------

@router.get("/_sections")
def vfs_sections(
    include_empty: bool = Query(default=False, description="Include entity types with zero active entities"),
    db=Depends(get_db),
):
    cfg_res = (
        db.table("entity_type_config")
        .select("id, config, approval_status")
        .eq("approval_status", "approved")
        .order("id")
        .execute()
    )
    rows = cfg_res.data or []

    sections: list[dict[str, object]] = []
    for row in rows:
        entity_type = str(row.get("id") or "").strip()
        if not entity_type:
            continue
        # Keep browse focused on operational entities; document records remain
        # queryable/searchable but are excluded from the left browse navigation.
        if entity_type == "document":
            continue
        cfg = row.get("config") if isinstance(row.get("config"), dict) else {}
        count = _count_active_entities(db, entity_type=entity_type)
        if not include_empty and count == 0:
            continue

        segment = segment_from_type(entity_type)
        label = cfg.get("browse_label") if isinstance(cfg.get("browse_label"), str) else None
        if not label:
            label = _titleize_slug(segment)
        sections.append(
            {
                "path": f"/{segment}",
                "label": label,
                "types": [entity_type],
                "count": count,
            }
        )

    total_entities = sum(int(s["count"]) for s in sections)
    return {
        "sections": sections,
        "total_sections": len(sections),
        "total_entities": total_entities,
    }


# ---------------------------------------------------------------------------
# GET /vfs/_glob — path-pattern search
# ---------------------------------------------------------------------------

@router.get("/_glob", response_model=VfsListResponse)
def vfs_glob(
    pattern: str = Query(..., description="Glob pattern, e.g. /companies/**/deals"),
    limit: int = Query(default=200, ge=1, le=500),
    db=Depends(get_db),
):
    res = _list_active_entities(db, limit=limit, glob=pattern)
    rows = res.data or []
    nodes = [_entity_to_vfs_node(e, "") for e in rows]
    return VfsListResponse(path=pattern, children=nodes, total=len(nodes))


# ---------------------------------------------------------------------------
# GET /vfs/{path} — list or detail
# ---------------------------------------------------------------------------

@router.get("/{path:path}", response_model=VfsNode | VfsListResponse)
def vfs_read(
    path: str,
    glob: str | None = Query(default=None, description="Glob filter pattern"),
    as_of: datetime | None = Query(default=None),
    db=Depends(get_db),
):
    segments = _path_segments(path)

    # --- Direct path lookup via attrs.vfs_path ---
    direct = db.table("entities").select("*").eq(
        "attrs->>vfs_path", f"/{path}"
    ).limit(1).execute()
    if direct.data:
        e = direct.data[0]
        return _entity_to_vfs_node(e, f"/{path}")

    # --- Segment-based routing ---
    if not segments:
        # Root: list all top-level types
        raise HTTPException(status_code=400, detail="Specify a type segment, e.g. /vfs/companies")

    type_key = segments[0]
    entity_type = _COLLECTION_ALIASES.get(type_key, type_from_segment(type_key))

    if len(segments) == 1:
        # List all entities of this type
        res = _list_active_entities(db, entity_type=entity_type, limit=500, glob=glob)
        nodes = [
            _entity_to_vfs_node(
                e,
                f"/{segment_from_type(str(e['entity_type']))}/{e['id']}",
            )
            for e in (res.data or [])
        ]

        # Lightweight augmentation: for communication lists, attach sentiment label if present.
        if entity_type == "communication" and nodes:
            try:
                ids = [n.entity_id for n in nodes]
                f_res = (
                    db.table("facts")
                    .select("subject_id, object_literal")
                    .eq("predicate", "sentiment")
                    .is_("valid_to", "null")
                    .in_("subject_id", ids)
                    .execute()
                )
                labels: dict[str, tuple[str, float | None]] = {}
                for f in f_res.data or []:
                    lit = f.get("object_literal")
                    label = None
                    conf = None
                    if isinstance(lit, dict):
                        raw = lit.get("label") or lit.get("value")
                        if isinstance(raw, str):
                            label = raw.strip()
                        if isinstance(lit.get("confidence"), (int, float)):
                            conf = float(lit.get("confidence"))
                    elif isinstance(lit, str):
                        label = lit.strip()
                    if label:
                        labels[str(f.get("subject_id"))] = (label, conf)
                if labels:
                    for n in nodes:
                        if n.entity_id in labels:
                            lab, cf = labels[n.entity_id]
                            n.content["sentiment_label"] = lab
                            if cf is not None:
                                n.content["sentiment_confidence"] = cf
            except Exception:
                pass  # best-effort; list remains usable without augmentation

        return VfsListResponse(path=f"/{path}", children=nodes, total=len(nodes))

    slug = segments[1]

    # Look up entity by ID or canonical_name slug
    e_res = None
    try:
        uuid.UUID(slug)
        e_res = db.table("entities").select("*").eq("id", slug).eq("entity_type", entity_type).single().execute()
    except ValueError:
        pass

    if not e_res or not e_res.data:
        # fuzzy name lookup
        e_res = db.table("entities").select("*").eq("entity_type", entity_type).ilike(
            "canonical_name", f"%{slug.replace('-', ' ')}%"
        ).limit(1).execute()
        if e_res.data:
            e_res.data = e_res.data[0]  # type: ignore[assignment]
        else:
            raise HTTPException(status_code=404, detail=f"Node not found: /{path}")

    entity = e_res.data if isinstance(e_res.data, dict) else e_res.data
    if not entity:
        raise HTTPException(status_code=404, detail=f"Node not found: /{path}")

    if len(segments) == 2:
        return _entity_to_vfs_node(entity, f"/{path}")

    # Nested: /companies/{slug}/deals → traverse via facts
    child_type_key = segments[2]
    child_type = _COLLECTION_ALIASES.get(child_type_key, type_from_segment(child_type_key))
    entity_id = str(entity["id"])

    facts_res = db.table("facts").select("object_id, subject_id").or_(
        f"subject_id.eq.{entity_id},object_id.eq.{entity_id}"
    ).is_("valid_to", "null").execute()
    neighbor_ids = set()
    for f in facts_res.data or []:
        if str(f.get("subject_id")) != entity_id and f.get("subject_id"):
            neighbor_ids.add(str(f["subject_id"]))
        if str(f.get("object_id")) != entity_id and f.get("object_id"):
            neighbor_ids.add(str(f["object_id"]))

    if not neighbor_ids:
        return VfsListResponse(path=f"/{path}", children=[], total=0)

    neighbors_res = db.table("entities").select("*").eq("entity_type", child_type).in_(
        "id", list(neighbor_ids)
    ).execute()
    nodes = [
        _entity_to_vfs_node(e, f"/{type_key}/{slug}/{child_type_key}/{e['id']}")
        for e in (neighbors_res.data or [])
    ]
    return VfsListResponse(path=f"/{path}", children=nodes, total=len(nodes))


# ---------------------------------------------------------------------------
# POST /vfs/propose-fact — write a fact into the layer
# ---------------------------------------------------------------------------

@router.post("/propose-fact", response_model=ProposeFactResponse, status_code=201)
def propose_fact(req: ProposeFactRequest, db=Depends(get_db)):
    now = datetime.now(tz=timezone.utc).isoformat()

    # 1. Create SourceRecord for audit trail
    sr_id = str(uuid.uuid4())
    sr_payload = {
        "id": sr_id,
        "source_type": req.source_system,
        "source_id": f"{req.source_system}:{sr_id}",
        "event_type": "fact_proposal",
        "raw_content": req.note or f"Proposed: {req.predicate}",
        "timestamp": now,
        "metadata": {
            "method": req.source_method,
            "proposed_by": req.source_system,
        },
    }
    try:
        db.table("source_records").insert(sr_payload).execute()
    except Exception as exc:
        logger.exception("source_records insert failed in propose_fact: %s", exc)
        raise HTTPException(status_code=500, detail=f"source_records insert failed: {exc}")

    # 2. Create Fact (supersede trigger fires automatically in Postgres)
    fact_id = str(uuid.uuid4())
    fact_payload = {
        "id": fact_id,
        "subject_id": req.subject_id,
        "predicate": req.predicate,
        "object_id": req.object_id,
        "object_literal": req.object_literal,
        "confidence": req.confidence,
        "source_id": sr_id,
        "derivation": f"{req.source_method}",
        "valid_from": now,
        "status": "live",
    }
    try:
        db.table("facts").insert(fact_payload).execute()
    except Exception as exc:
        logger.exception("facts insert failed in propose_fact: %s", exc)
        raise HTTPException(status_code=500, detail=f"facts insert failed: {exc}")

    return ProposeFactResponse(fact_id=fact_id, source_record_id=sr_id)


# ---------------------------------------------------------------------------
# PATCH /vfs/{path} — update individual attrs without touching facts
# ---------------------------------------------------------------------------


@router.patch("/{path:path}", response_model=VfsPatchResponse)
def vfs_patch(path: str, req: VfsPatchRequest, db=Depends(get_db)):
    """Merge attrs changes into an entity.

    Keys with non-null values are set; keys with null values are removed.
    Facts and the entity row's other fields are not touched.
    """
    segments = _path_segments(path)
    if len(segments) < 2:
        raise HTTPException(status_code=400, detail="Provide a specific entity path, e.g. /companies/acme")

    type_key = segments[0]
    entity_type = _COLLECTION_ALIASES.get(type_key, type_from_segment(type_key))
    slug = segments[1]

    e_res = _get_active_entity_for_patch(db, slug=slug, entity_type=entity_type)
    if e_res.data and isinstance(e_res.data, list):
        e_res.data = e_res.data[0]  # type: ignore[assignment]

    if not e_res.data:
        raise HTTPException(status_code=404, detail=f"Entity not found: /{path}")

    entity_id = str(e_res.data["id"])
    current_attrs = dict(e_res.data.get("attrs") or {})

    updated: list[str] = []
    removed: list[str] = []
    new_attrs = dict(current_attrs)

    for key, value in req.attrs.items():
        if value is None:
            if key in new_attrs:
                del new_attrs[key]
                removed.append(key)
        else:
            new_attrs[key] = value
            updated.append(key)

    if not updated and not removed:
        raise HTTPException(status_code=422, detail="No attr changes provided")

    now = datetime.now(tz=timezone.utc).isoformat()

    sr_id = str(uuid.uuid4())
    db.table("source_records").insert({
        "id": sr_id,
        "source_type": "human_patch",
        "source_id": f"patch:{entity_id}",
        "event_type": "attrs_patch",
        "raw_content": req.reason or f"VFS patch: /{path}",
        "timestamp": now,
        "metadata": {
            "method": "human_patch",
            "path": path,
            "updated": updated,
            "removed": removed,
        },
    }).execute()

    db.table("entities").update({"attrs": new_attrs}).eq("id", entity_id).execute()

    return VfsPatchResponse(
        path=f"/{path}",
        entity_id=entity_id,
        attrs_updated=updated,
        attrs_removed=removed,
        audit_record=sr_id,
    )


# ---------------------------------------------------------------------------
# DELETE /vfs/{path} — mark all active facts for entity as invalid
# ---------------------------------------------------------------------------

@router.delete("/{path:path}", status_code=200)
def vfs_delete(path: str, reason: str | None = Query(default=None), db=Depends(get_db)):
    segments = _path_segments(path)
    if len(segments) < 2:
        raise HTTPException(status_code=400, detail="Provide a specific entity path to delete")

    type_key = segments[0]
    entity_type = _COLLECTION_ALIASES.get(type_key, type_from_segment(type_key))
    slug = segments[1]

    # Resolve entity
    try:
        uuid.UUID(slug)
        e_res = db.table("entities").select("id").eq("id", slug).single().execute()
    except ValueError:
        e_res = db.table("entities").select("id").eq("entity_type", entity_type).ilike(
            "canonical_name", f"%{slug.replace('-', ' ')}%"
        ).limit(1).execute()
        if e_res.data:
            e_res.data = e_res.data[0]  # type: ignore[assignment]

    if not e_res.data:
        raise HTTPException(status_code=404, detail=f"Entity not found: /{path}")

    entity_id = str(e_res.data["id"])
    now = datetime.now(tz=timezone.utc).isoformat()

    # Create audit SourceRecord
    sr_id = str(uuid.uuid4())
    db.table("source_records").insert({
        "id": sr_id,
        "source_type": "human_delete",
        "source_id": f"delete:{entity_id}",
        "event_type": "fact_deletion",
        "raw_content": reason or f"VFS delete: /{path}",
        "timestamp": now,
        "metadata": {"method": "human_delete", "path": path},
    }).execute()

    # Invalidate all live facts where entity is subject (outgoing edges)
    out_res = db.table("facts").update({
        "valid_to": now,
        "status": "superseded",
    }).eq("subject_id", entity_id).is_("valid_to", "null").execute()

    # Invalidate all live facts where entity is object (incoming edges)
    in_res = db.table("facts").update({
        "valid_to": now,
        "status": "superseded",
    }).eq("object_id", entity_id).is_("valid_to", "null").execute()

    try:
        db.table("entities").update({"deleted_at": now, "status": "archived"}).eq("id", entity_id).execute()
    except Exception as exc:
        if not _missing_column(exc, "deleted_at"):
            raise
        logger.warning("entities.deleted_at missing; falling back to status-only archival in vfs delete")
        db.table("entities").update({"status": "archived"}).eq("id", entity_id).execute()

    invalidated = (len(out_res.data) if out_res.data else 0) + (
        len(in_res.data) if in_res.data else 0
    )
    return {"deleted_path": f"/{path}", "facts_invalidated": invalidated, "audit_record": sr_id}
