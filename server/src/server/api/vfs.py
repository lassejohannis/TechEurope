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

_COLLECTION_ALIASES: dict[str, str] = {
    "contacts": "person",
}

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
# GET /vfs/_glob — path-pattern search
# ---------------------------------------------------------------------------

@router.get("/_glob", response_model=VfsListResponse)
def vfs_glob(
    pattern: str = Query(..., description="Glob pattern, e.g. /companies/**/deals"),
    limit: int = Query(default=200, ge=1, le=500),
    db=Depends(get_db),
):
    ilike_pattern = glob_to_ilike(pattern)
    res = (
        db.table("entities")
        .select("*")
        .ilike("attrs->>vfs_path", ilike_pattern)
        .is_("deleted_at", "null")
        .limit(limit)
        .execute()
    )
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
        q = db.table("entities").select("*").eq("entity_type", entity_type).is_("deleted_at", "null").limit(100)
        if glob:
            q = q.ilike("attrs->>vfs_path", glob_to_ilike(glob))
        res = q.execute()
        nodes = [
            _entity_to_vfs_node(
                e,
                f"/{segment_from_type(str(e['entity_type']))}/{e['id']}",
            )
            for e in (res.data or [])
        ]
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
    db.table("source_records").insert(sr_payload).execute()

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
        "status": "active",
    }
    db.table("facts").insert(fact_payload).execute()

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

    try:
        uuid.UUID(slug)
        e_res = db.table("entities").select("id, attrs").eq("id", slug).is_("deleted_at", "null").single().execute()
    except ValueError:
        e_res = db.table("entities").select("id, attrs").eq("entity_type", entity_type).ilike(
            "canonical_name", f"%{slug.replace('-', ' ')}%"
        ).is_("deleted_at", "null").limit(1).execute()
        if e_res.data:
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
        "status": "invalidated",
    }).eq("subject_id", entity_id).is_("valid_to", "null").execute()

    # Invalidate all live facts where entity is object (incoming edges)
    in_res = db.table("facts").update({
        "valid_to": now,
        "status": "invalidated",
    }).eq("object_id", entity_id).is_("valid_to", "null").execute()

    # Soft-delete the entity row — fires Supabase Realtime UPDATE event so
    # the Neo4j projection sees deleted_at and DETACH DELETEs the node.
    db.table("entities").update({"deleted_at": now}).eq("id", entity_id).execute()

    invalidated = (len(out_res.data) if out_res.data else 0) + (
        len(in_res.data) if in_res.data else 0
    )
    return {"deleted_path": f"/{path}", "facts_invalidated": invalidated, "audit_record": sr_id}
