"""POST /query/traverse — Graph traversal via JSON-DSL (Req 7.2).

DSL example:
  {
    "start": {"entity_type": "company", "canonical_name": "Acme"},
    "steps": [
      {"predicate": "works_at", "direction": "inbound", "target_type": "person"}
    ],
    "max_depth": 2,
    "min_confidence": 0.7,
    "limit": 30
  }

Directions: "outbound" follows subject→object, "inbound" follows object→subject, "both" follows either.
Predicate "*" matches any predicate.
Steps are applied in sequence; the last step is reused for remaining depth levels.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.db import get_db
from server.models import EntityResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["graph"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TraverseStart(BaseModel):
    entity_id: str | None = None
    entity_ids: list[str] | None = None
    entity_type: str | None = None
    canonical_name: str | None = None  # substring match


class TraverseStep(BaseModel):
    predicate: str = "*"
    direction: Literal["outbound", "inbound", "both"] = "outbound"
    target_type: str | None = None


class TraverseRequest(BaseModel):
    start: TraverseStart
    steps: list[TraverseStep] = Field(default_factory=lambda: [TraverseStep()])
    max_depth: int = Field(default=1, ge=1, le=4)
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    as_of: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)


class TraverseEdge(BaseModel):
    fact_id: str
    source_id: str
    target_id: str
    predicate: str
    direction: str
    confidence: float


class TraverseResponse(BaseModel):
    start_entity_ids: list[str]
    nodes: list[EntityResponse]
    edges: list[TraverseEdge]
    total_nodes: int
    total_edges: int
    depth_reached: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_start_entities(db, start: TraverseStart) -> list[str]:
    if start.entity_id:
        return [start.entity_id]
    if start.entity_ids:
        return list(start.entity_ids)

    q = db.table("entities").select("id")
    if start.entity_type:
        q = q.eq("entity_type", start.entity_type)
    if start.canonical_name:
        q = q.ilike("canonical_name", f"%{start.canonical_name}%")
    res = q.limit(10).execute()
    return [str(r["id"]) for r in (res.data or [])]


def _hop(
    db,
    entity_id: str,
    step: TraverseStep,
    min_confidence: float,
    as_of: datetime | None,
) -> list[TraverseEdge]:
    edges: list[TraverseEdge] = []
    directions = ["outbound", "inbound"] if step.direction == "both" else [step.direction]

    for direction in directions:
        try:
            if direction == "outbound":
                q = (
                    db.table("facts")
                    .select("id, subject_id, object_id, predicate, confidence")
                    .eq("subject_id", entity_id)
                    .not_.is_("object_id", "null")
                )
            else:
                q = (
                    db.table("facts")
                    .select("id, subject_id, object_id, predicate, confidence")
                    .eq("object_id", entity_id)
                )

            if step.predicate != "*":
                q = q.eq("predicate", step.predicate)
            if min_confidence > 0:
                q = q.gte("confidence", min_confidence)
            if as_of:
                q = q.lte("valid_from", as_of.isoformat()).or_(
                    f"valid_to.is.null,valid_to.gte.{as_of.isoformat()}"
                )
            else:
                q = q.is_("valid_to", "null")

            for row in q.limit(50).execute().data or []:
                target = row["object_id"] if direction == "outbound" else row["subject_id"]
                if target:
                    edges.append(TraverseEdge(
                        fact_id=str(row["id"]),
                        source_id=entity_id,
                        target_id=str(target),
                        predicate=row["predicate"],
                        direction=direction,
                        confidence=float(row.get("confidence") or 0),
                    ))
        except Exception as exc:
            logger.debug("Hop error (entity=%s dir=%s): %s", entity_id, direction, exc)

    return edges


def _fetch_entity(db, entity_id: str) -> EntityResponse | None:
    try:
        e = db.table("entities").select("*").eq("id", entity_id).single().execute()
        if not e.data:
            return None
        t = db.table("entity_trust").select("*").eq("id", entity_id).single().execute()
        td = t.data or {}
        return EntityResponse(
            id=str(e.data["id"]),
            entity_type=e.data["entity_type"],
            canonical_name=e.data["canonical_name"],
            aliases=e.data.get("aliases") or [],
            attrs=e.data.get("attrs") or {},
            trust_score=float(td.get("trust_score") or 0),
            fact_count=int(td.get("fact_count") or 0),
            source_diversity=int(td.get("source_diversity") or 0),
        )
    except Exception as exc:
        logger.debug("Entity fetch failed %s: %s", entity_id, exc)
        return None


def _matches_target_type(db, entity_id: str, target_type: str) -> bool:
    try:
        res = db.table("entities").select("entity_type").eq("id", entity_id).single().execute()
        return bool(res.data and res.data.get("entity_type") == target_type)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/query/traverse", response_model=TraverseResponse)
def traverse(req: TraverseRequest, db=Depends(get_db)):
    """Graph traversal with a JSON-DSL.

    Follow edges from start entities step-by-step, up to max_depth hops.
    Each step defines which predicate/direction/target-type to follow.
    The last step is reused for any additional depth levels.

    Response includes all visited nodes (with trust scores) and traversed edges.
    """
    if not req.steps:
        raise HTTPException(status_code=400, detail="At least one step required")

    start_ids = _find_start_entities(db, req.start)
    if not start_ids:
        return TraverseResponse(
            start_entity_ids=[],
            nodes=[],
            edges=[],
            total_nodes=0,
            total_edges=0,
            depth_reached=0,
        )

    visited: set[str] = set(start_ids)
    all_edges: list[TraverseEdge] = []
    frontier = list(start_ids)
    depth_reached = 0

    for depth_idx in range(req.max_depth):
        step = req.steps[min(depth_idx, len(req.steps) - 1)]
        next_frontier: list[str] = []

        for eid in frontier:
            for edge in _hop(db, eid, step, req.min_confidence, req.as_of):
                target = edge.target_id
                if target in visited or len(visited) >= req.limit:
                    continue
                if step.target_type and not _matches_target_type(db, target, step.target_type):
                    continue
                visited.add(target)
                next_frontier.append(target)
                all_edges.append(edge)

        if not next_frontier:
            break
        frontier = next_frontier
        depth_reached = depth_idx + 1

    nodes = [e for eid in visited if (e := _fetch_entity(db, eid)) is not None]

    return TraverseResponse(
        start_entity_ids=start_ids,
        nodes=nodes,
        edges=all_edges,
        total_nodes=len(nodes),
        total_edges=len(all_edges),
        depth_reached=depth_reached,
    )
