"""POST /query/cypher — Proxy to Neo4j read-only projection (WS-5).

Returns 503 with a clear banner when Neo4j is not configured.
The Revenue App and Frontend can check this endpoint and degrade gracefully.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.config import settings

# DEMO_QUERIES live in the WS-5 sync module — import lazily so missing neo4j dep doesn't break startup
try:
    from server.sync.neo4j_projection import DEMO_QUERIES  # type: ignore
except ImportError:
    DEMO_QUERIES: dict[str, str] = {}

router = APIRouter(prefix="/query", tags=["graph"])


class CypherRequest(BaseModel):
    query: str | None = None
    named_query: str | None = None  # key into DEMO_QUERIES
    params: dict = {}


class CypherResponse(BaseModel):
    rows: list[dict]
    columns: list[str]
    query_used: str


def _neo4j_available() -> bool:
    return bool(settings.neo4j_uri and settings.neo4j_password)


@router.post("/cypher", response_model=CypherResponse)
async def run_cypher(req: CypherRequest):
    if not _neo4j_available():
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Neo4j projection not available — Postgres-only mode active.",
                "day_2_feature": True,
                "available_named_queries": list(DEMO_QUERIES.keys()),
            },
        )

    cypher = req.query
    if not cypher and req.named_query:
        cypher = DEMO_QUERIES.get(req.named_query)
    if not cypher:
        raise HTTPException(status_code=400, detail="Provide 'query' or 'named_query'")

    try:
        from neo4j import AsyncGraphDatabase  # type: ignore
        driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        async with driver.session() as session:
            result = await session.run(cypher, req.params)
            records = await result.data()
            keys = list(records[0].keys()) if records else []

        await driver.close()
        return CypherResponse(rows=records, columns=keys, query_used=cypher)

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Neo4j error: {exc}") from exc


@router.get("/cypher/named", tags=["graph"])
def list_named_queries():
    """Return available pre-built demo Cypher queries."""
    return {
        "available": list(DEMO_QUERIES.keys()),
        "neo4j_ready": _neo4j_available(),
    }
