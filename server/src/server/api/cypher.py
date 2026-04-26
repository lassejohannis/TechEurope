"""Read-only Cypher endpoint for the Neo4j projection (WS-5).

Exposes the three pre-baked demo queries from
`server.sync.neo4j_projection.DEMO_QUERIES`. Generic Cypher is intentionally
not accepted here — WS-4 owns the broader query API.

When the projection isn't configured (empty `NEO4J_URI`), the routes return
503 with an honest message so the rest of the app keeps running
Postgres-only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from server.sync.neo4j_projection import DEMO_QUERIES, Neo4jProjection

router = APIRouter(prefix="/query/cypher", tags=["cypher"])


def _projection(request: Request) -> Neo4jProjection:
    proj: Neo4jProjection | None = getattr(request.app.state, "projection", None)
    if proj is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j projection unavailable — running Postgres-only mode.",
        )
    return proj


@router.get("/_health")
async def health(request: Request) -> dict[str, Any]:
    proj: Neo4jProjection | None = getattr(request.app.state, "projection", None)
    if proj is None:
        return {"status": "down", "reason": "neo4j not configured"}
    return await proj.healthcheck()


@router.get("/demo")
async def list_demos() -> dict[str, list[str]]:
    return {"queries": list(DEMO_QUERIES.keys())}


@router.get("/demo/{name}")
async def run_demo(
    name: str,
    request: Request,
    from_id: str | None = None,
    to_id: str | None = None,
) -> dict[str, Any]:
    if name not in DEMO_QUERIES:
        raise HTTPException(
            status_code=404,
            detail=f"unknown demo query; available: {list(DEMO_QUERIES.keys())}",
        )
    proj = _projection(request)
    if proj.driver is None:
        raise HTTPException(status_code=503, detail="projection driver missing")
    cypher = DEMO_QUERIES[name]
    params = {k: v for k, v in {"from_id": from_id, "to_id": to_id}.items() if v}
    async with proj.driver.session(database=proj.cfg.neo4j_database) as session:
        result = await session.run(cypher, params)
        rows = [r.data() async for r in result]
    return {"name": name, "rows": rows, "row_count": len(rows)}
