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
    ProposeFactResponse, VfsListResponse, VfsNode,
)

router = APIRouter(prefix="/vfs", tags=["vfs"])

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_SLUG_TO_TYPE = {
    "companies": "company",
    "persons": "person",
    "contacts": "person",
    "deals": "deal",
    "documents": "document",
    "communications": "communication",
    "products": "product",
}

_TYPE_TO_SLUG = {v: k for k, v in _SLUG_TO_TYPE.items()}


def _entity_to_vfs_node(e: dict, path: str) -> VfsNode:
    attrs = e.get("attrs") or {}
    return VfsNode(
        path=attrs.get("vfs_path", path),
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
    entity_type = _SLUG_TO_TYPE.get(type_key)

    if entity_type is None:
        # Try as entity_type directly
        entity_type = type_key

    if len(segments) == 1:
        # List all entities of this type
        q = db.table("entities").select("*").eq("entity_type", entity_type).limit(100)
        if glob:
            q = q.ilike("canonical_name", glob.replace("*", "%"))
        res = q.execute()
        nodes = [_entity_to_vfs_node(e, f"/{type_key}/{e['id']}") for e in (res.data or [])]
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
    child_type = _SLUG_TO_TYPE.get(child_type_key, child_type_key)
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
# DELETE /vfs/{path} — mark all active facts for entity as invalid
# ---------------------------------------------------------------------------

@router.delete("/{path:path}", status_code=200)
def vfs_delete(path: str, reason: str | None = Query(default=None), db=Depends(get_db)):
    segments = _path_segments(path)
    if len(segments) < 2:
        raise HTTPException(status_code=400, detail="Provide a specific entity path to delete")

    type_key = segments[0]
    entity_type = _SLUG_TO_TYPE.get(type_key, type_key)
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

    # Mark all active facts invalid
    result = db.table("facts").update({
        "valid_to": now,
        "status": "invalidated",
    }).eq("subject_id", entity_id).is_("valid_to", "null").execute()

    invalidated = len(result.data) if result.data else 0
    return {"deleted_path": f"/{path}", "facts_invalidated": invalidated, "audit_record": sr_id}
