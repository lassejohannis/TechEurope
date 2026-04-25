"""POST /query/cypher — Proxy to Neo4j read-only projection (WS-5).

Returns 503 with a clear banner when Neo4j is not configured.
The Revenue App and Frontend can check this endpoint and degrade gracefully.
"""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from server.config import settings

# Cypher write-operation keywords — block these to enforce read-only access.
_WRITE_PATTERN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH\s+DELETE|SET\s|REMOVE\s|DROP\s|CALL\s+apoc\.schema|CALL\s+apoc\.periodic\.commit)\b",
    re.IGNORECASE,
)


def _assert_read_only(cypher: str) -> None:
    m = _WRITE_PATTERN.search(cypher)
    if m:
        raise HTTPException(
            status_code=400,
            detail=f"Write operations are not allowed on this endpoint (found: '{m.group().strip()}').",
        )

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


def _sanitize(value: object) -> object:
    """Recursively convert neo4j driver types to JSON-serializable Python types."""
    if isinstance(value, dict):
        return {k: _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    # neo4j.time types (DateTime, Date, Time, Duration) and neo4j.graph types
    # all implement __str__ in a sensible ISO format.
    module = type(value).__module__ or ""
    if module.startswith("neo4j"):
        return str(value)
    return value


def _pg_graph_fallback(req: CypherRequest) -> CypherResponse:
    """Serve graph data from Postgres facts+entities when Neo4j is not configured."""
    from server.db import get_supabase
    db = get_supabase()

    limit = min(300, max(1, int(req.params.get("limit", 80))))
    focus_id = str(req.params.get("focus_id", "") or "")

    q = (
        db.table("facts")
        .select("subject_id, object_id, predicate")
        .filter("object_id", "not.is", "null")
        .is_("valid_to", "null")
        .limit(limit)
    )
    if focus_id:
        q = q.or_(f"subject_id.eq.{focus_id},object_id.eq.{focus_id}")
    facts = (q.execute().data) or []

    entity_ids = list({str(f["subject_id"]) for f in facts} | {str(f["object_id"]) for f in facts})
    if not entity_ids:
        return CypherResponse(rows=[], columns=[], query_used="pg_fallback")

    entities_res = (
        db.table("entities")
        .select("id, canonical_name, entity_type, attrs")
        .in_("id", entity_ids)
        .execute()
    )
    entity_map = {str(e["id"]): e for e in (entities_res.data or [])}

    columns = [
        "source_id", "source_label", "source_type", "source_labels", "source_props",
        "target_id", "target_label", "target_type", "target_labels", "target_props", "rel_type",
    ]
    rows = []
    for f in facts:
        sid, oid = str(f["subject_id"]), str(f["object_id"])
        src, tgt = entity_map.get(sid), entity_map.get(oid)
        if not src or not tgt:
            continue
        rows.append({
            "source_id": sid,
            "source_label": src.get("canonical_name") or sid,
            "source_type": src.get("entity_type") or "entity",
            "source_labels": [src.get("entity_type") or "Entity"],
            "source_props": src.get("attrs") or {},
            "target_id": oid,
            "target_label": tgt.get("canonical_name") or oid,
            "target_type": tgt.get("entity_type") or "entity",
            "target_labels": [tgt.get("entity_type") or "Entity"],
            "target_props": tgt.get("attrs") or {},
            "rel_type": f.get("predicate") or "REL",
        })
    return CypherResponse(rows=rows, columns=columns, query_used="pg_fallback:facts+entities")


@router.post("/cypher", response_model=CypherResponse)
async def run_cypher(req: CypherRequest):
    if not _neo4j_available():
        return _pg_graph_fallback(req)

    cypher = req.query
    if not cypher and req.named_query:
        cypher = DEMO_QUERIES.get(req.named_query)
    if not cypher:
        raise HTTPException(status_code=400, detail="Provide 'query' or 'named_query'")

    _assert_read_only(cypher)

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
        return CypherResponse(rows=[_sanitize(r) for r in records], columns=keys, query_used=cypher)

    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Neo4j error: {exc}") from exc


@router.get("/cypher/named", tags=["graph"])
def list_named_queries():
    """Return available pre-built demo Cypher queries."""
    return {
        "available": list(DEMO_QUERIES.keys()),
        "neo4j_ready": _neo4j_available(),
    }
