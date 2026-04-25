"""MCP Server — 6 tools mapped to the Query API.

Mounted at /mcp in main.py via mcp.sse_app().

Tools:
  search_memory         3-Stage Hybrid Search
  get_entity            Full entity card + trust score
  get_fact              Single fact + provenance
  get_fact_provenance   On-demand evidence chain
  list_recent_changes   Change feed since timestamp
  propose_fact          Agent-driven fact submission
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from server.api.search import run_hybrid_search
from server.db import get_db
from server.models import ProposeFactRequest

logger = logging.getLogger(__name__)

mcp = FastMCP(
    name="qontext-context-engine",
    instructions=(
        "Context Engine MCP interface. "
        "Use search_memory for discovery, get_entity/get_fact for detail, "
        "propose_fact to write new facts into the layer."
    ),
)


# ---------------------------------------------------------------------------
# Tool: search_memory
# ---------------------------------------------------------------------------

@mcp.tool()
def search_memory(query: str, k: int = 10, entity_type: str | None = None) -> list[dict[str, Any]]:
    """3-Stage Hybrid Search (Semantic ∩ Structural → Rerank).

    Args:
        query: Natural-language search query
        k: Maximum number of results to return (1-50)
        entity_type: Optional filter by entity type (person/company/deal/…)

    Returns list of EntityResponse dicts ordered by relevance score.
    """
    results = run_hybrid_search(query=query, k=k, entity_type=entity_type)
    return [r.model_dump() for r in results]


# ---------------------------------------------------------------------------
# Tool: get_entity
# ---------------------------------------------------------------------------

@mcp.tool()
def get_entity(entity_id: str) -> dict[str, Any] | None:
    """Return full entity card: canonical_name, type, attrs, trust_score, active facts.

    Args:
        entity_id: UUID of the entity
    """
    db = get_db()
    e_res = db.table("entities").select("*").eq("id", entity_id).single().execute()
    if not e_res.data:
        return None

    trust_res = db.table("entity_trust").select("*").eq("id", entity_id).single().execute()
    facts_res = db.table("facts").select("*").eq("subject_id", entity_id).is_("valid_to", "null").execute()

    entity = dict(e_res.data)
    entity["trust_score"] = float(trust_res.data["trust_score"]) if trust_res.data else 0.0
    entity["facts"] = facts_res.data or []
    return entity


# ---------------------------------------------------------------------------
# Tool: get_fact
# ---------------------------------------------------------------------------

@mcp.tool()
def get_fact(fact_id: str) -> dict[str, Any] | None:
    """Return a single fact with its source record for provenance.

    Args:
        fact_id: UUID of the fact
    """
    db = get_db()
    res = db.table("facts").select("*, source_records(*)").eq("id", fact_id).single().execute()
    return res.data or None


# ---------------------------------------------------------------------------
# Tool: get_fact_provenance
# ---------------------------------------------------------------------------

@mcp.tool()
def get_fact_provenance(fact_id: str) -> dict[str, Any] | None:
    """On-demand full evidence chain: fact → source record → raw content.

    Fulfils Requirement 5.4: dedicated provenance tool.

    Args:
        fact_id: UUID of the fact
    """
    db = get_db()
    res = db.rpc("get_fact_provenance_json", {"p_fact_id": fact_id}).execute()
    if res.data:
        return res.data
    # Fallback: manual join
    return get_fact(fact_id)


# ---------------------------------------------------------------------------
# Tool: list_recent_changes
# ---------------------------------------------------------------------------

@mcp.tool()
def list_recent_changes(since: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Return recently created or superseded facts (change feed).

    Args:
        since: ISO-8601 timestamp. Defaults to last 24h.
        limit: Maximum number of events (1-100)
    """
    db = get_db()
    since_ts = since or datetime.now(tz=timezone.utc).replace(
        hour=0, minute=0, second=0
    ).isoformat()

    res = db.table("facts").select(
        "id, subject_id, predicate, object_id, object_literal, confidence, "
        "derivation, valid_from, valid_to, recorded_at, superseded_by, status"
    ).gte("recorded_at", since_ts).order("recorded_at", desc=True).limit(min(limit, 100)).execute()

    return res.data or []


# ---------------------------------------------------------------------------
# Tool: propose_fact
# ---------------------------------------------------------------------------

@mcp.tool()
def propose_fact(
    subject_id: str,
    predicate: str,
    object_id: str | None = None,
    object_literal: Any = None,
    confidence: float = 1.0,
    source_system: str = "agent",
    note: str | None = None,
) -> dict[str, Any]:
    """Submit a new fact into the context layer (agent-driven write).

    Creates a SourceRecord for audit trail + a Fact via the supersede pipeline.
    The Postgres supersede-trigger auto-closes any existing fact for the same
    (subject, predicate) pair.

    Args:
        subject_id: UUID of the subject entity
        predicate: Relationship predicate string (e.g. "champion_of")
        object_id: UUID of object entity (for entity→entity facts)
        object_literal: JSON-serialisable value (for scalar facts)
        confidence: 0.0–1.0
        source_system: Identifier for the agent/system proposing this fact
        note: Optional human-readable explanation
    """
    from server.api.vfs import propose_fact as _propose  # avoid circular at module level

    req = ProposeFactRequest(
        subject_id=subject_id,
        predicate=predicate,
        object_id=object_id,
        object_literal=object_literal,
        confidence=confidence,
        source_system=source_system,
        source_method="agent_input",
        note=note,
    )
    result = _propose(req, db=get_db())
    return result.model_dump()
