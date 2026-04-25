"""GET /graph/neighborhood/{entity_id} — N-hop subgraph as {nodes, edges}.

Postgres-only: BFS via repeated index scans on facts (cheap for depth<=2).
For depth>2 we'd want a recursive CTE — kept simple here since the demo
focuses on 1-hop neighbourhoods.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query

from server.auth import Principal, require_scope
from server.db import get_db

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/neighborhood/{entity_id}")
def neighborhood(
    entity_id: str,
    depth: int = Query(default=1, ge=1, le=3),
    edge_types: list[str] | None = Query(default=None),
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("read")),
) -> dict[str, Any]:
    """BFS up to `depth` hops from entity_id; returns deduplicated nodes + edges."""
    seed_res = db.table("entities").select("*").eq("id", entity_id).limit(1).execute()
    if not seed_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")

    nodes: dict[str, dict[str, Any]] = {entity_id: seed_res.data[0]}
    edges: list[dict[str, Any]] = []
    seen_edges: set[str] = set()
    frontier: set[str] = {entity_id}

    for _ in range(depth):
        if not frontier:
            break
        next_frontier: set[str] = set()
        # Outbound facts (subject in frontier, object_id != null, status active)
        out_q = (
            db.table("facts")
            .select("id, subject_id, predicate, object_id, confidence, status")
            .in_("subject_id", list(frontier))
            .not_.is_("object_id", "null")
            .is_("valid_to", "null")
        )
        if edge_types:
            out_q = out_q.in_("predicate", edge_types)
        for f in out_q.execute().data or []:
            if f["id"] in seen_edges:
                continue
            seen_edges.add(f["id"])
            edges.append({
                "id": f["id"],
                "source": f["subject_id"],
                "target": f["object_id"],
                "predicate": f["predicate"],
                "confidence": float(f.get("confidence") or 0),
            })
            target = f["object_id"]
            if target and target not in nodes:
                next_frontier.add(target)

        # Inbound facts
        in_q = (
            db.table("facts")
            .select("id, subject_id, predicate, object_id, confidence, status")
            .in_("object_id", list(frontier))
            .is_("valid_to", "null")
        )
        if edge_types:
            in_q = in_q.in_("predicate", edge_types)
        for f in in_q.execute().data or []:
            if f["id"] in seen_edges:
                continue
            seen_edges.add(f["id"])
            edges.append({
                "id": f["id"],
                "source": f["subject_id"],
                "target": f["object_id"],
                "predicate": f["predicate"],
                "confidence": float(f.get("confidence") or 0),
            })
            src = f["subject_id"]
            if src and src not in nodes:
                next_frontier.add(src)

        if next_frontier:
            res = db.table("entities").select("*").in_("id", list(next_frontier)).execute()
            for row in res.data or []:
                nodes[row["id"]] = row
        frontier = next_frontier

    return {
        "root": entity_id,
        "depth": depth,
        "nodes": list(nodes.values()),
        "edges": edges,
        "edge_count": len(edges),
        "node_count": len(nodes),
    }
