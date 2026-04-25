"""Smoke tests for the Neo4j read-only projection (WS-5).

Live Aura is required — set NEO4J_URI / NEO4J_PASSWORD in the env to run.
The tests bypass Postgres/Realtime entirely and exercise the upsert primitives
directly so WS-5 is verifiable independently of WS-0/WS-1/WS-2 progress.

Each test wipes its scratch namespace (`ws5-test:*`) before and after so they
are safe to re-run against a shared Aura instance.
"""

from __future__ import annotations

import pytest

from server.sync.neo4j_projection import (
    DEMO_QUERIES,
    Neo4jProjection,
    SyncConfig,
)
from tests.conftest import neo4j_creds_or_skip

pytestmark = pytest.mark.asyncio


def _cfg() -> SyncConfig:
    import os

    uri, user, password = neo4j_creds_or_skip()
    return SyncConfig(
        neo4j_uri=uri,
        neo4j_user=user,
        neo4j_password=password,
        neo4j_database=os.environ.get("NEO4J_DATABASE", "neo4j"),
        supabase_url="",
        supabase_secret_key="",
    )


async def _wipe(proj: Neo4jProjection) -> None:
    assert proj.driver
    async with proj.driver.session() as s:
        await s.run("MATCH (n:Entity) WHERE n.id STARTS WITH 'ws5-test:' DETACH DELETE n")


@pytest.fixture
async def projection():
    proj = Neo4jProjection(_cfg())
    await proj.start()
    await _wipe(proj)
    try:
        yield proj
    finally:
        await _wipe(proj)
        await proj.stop()


async def test_upsert_entity_then_fact(projection: Neo4jProjection) -> None:
    """Insert two entities + one fact, verify the edge exists."""
    await projection._upsert_entity(
        "INSERT",
        {
            "id": "ws5-test:acme",
            "entity_type": "company",
            "canonical_name": "Acme GmbH",
            "aliases": ["Acme", "Acme Corp"],
            "attrs": {"domain": "acme.test"},
        },
    )
    await projection._upsert_entity(
        "INSERT",
        {
            "id": "ws5-test:alice",
            "entity_type": "person",
            "canonical_name": "Alice",
            "aliases": [],
            "attrs": {},
        },
    )
    await projection._upsert_fact(
        "INSERT",
        {
            "id": "ws5-test:fact-1",
            "subject_id": "ws5-test:alice",
            "object_id": "ws5-test:acme",
            "predicate": "works_at",
            "confidence": 0.91,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None,
            "source_id": "ws5-test:src-1",
        },
    )

    assert projection.driver
    async with projection.driver.session() as s:
        result = await s.run(
            "MATCH (a:Entity {id:'ws5-test:alice'})-[r:WORKS_AT]->(b:Entity {id:'ws5-test:acme'}) "
            "RETURN r.confidence AS c, r.fact_id AS fid"
        )
        row = await result.single()
    assert row is not None
    assert row["c"] == pytest.approx(0.91)
    assert row["fid"] == "ws5-test:fact-1"


async def test_upsert_is_idempotent(projection: Neo4jProjection) -> None:
    """Running the same INSERT twice must produce a single edge."""
    payload = {
        "id": "ws5-test:fact-2",
        "subject_id": "ws5-test:alice",
        "object_id": "ws5-test:acme",
        "predicate": "manages",
        "confidence": 0.7,
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to": None,
        "source_id": "ws5-test:src-2",
    }
    for entity_id in ("ws5-test:alice", "ws5-test:acme"):
        await projection._upsert_entity(
            "INSERT",
            {"id": entity_id, "entity_type": "x", "canonical_name": entity_id},
        )
    await projection._upsert_fact("INSERT", payload)
    await projection._upsert_fact("INSERT", payload)

    assert projection.driver
    async with projection.driver.session() as s:
        result = await s.run(
            "MATCH (:Entity {id:'ws5-test:alice'})-[r:MANAGES {fact_id:'ws5-test:fact-2'}]->"
            "(:Entity {id:'ws5-test:acme'}) RETURN count(r) AS n"
        )
        row = await result.single()
    assert row is not None
    assert row["n"] == 1


async def test_delete_entity_detaches_edges(projection: Neo4jProjection) -> None:
    await projection._upsert_entity(
        "INSERT",
        {"id": "ws5-test:zombie", "entity_type": "person", "canonical_name": "Zombie"},
    )
    await projection._upsert_entity(
        "INSERT",
        {"id": "ws5-test:host", "entity_type": "company", "canonical_name": "Host"},
    )
    await projection._upsert_fact(
        "INSERT",
        {
            "id": "ws5-test:fact-3",
            "subject_id": "ws5-test:zombie",
            "object_id": "ws5-test:host",
            "predicate": "works_at",
            "confidence": 0.5,
            "valid_from": "2026-01-01T00:00:00Z",
            "valid_to": None,
            "source_id": "ws5-test:src-3",
        },
    )
    await projection._upsert_entity("DELETE", {"id": "ws5-test:zombie"})

    assert projection.driver
    async with projection.driver.session() as s:
        result = await s.run(
            "MATCH (n:Entity {id:'ws5-test:zombie'}) RETURN count(n) AS n"
        )
        row = await result.single()
    assert row is not None
    assert row["n"] == 0


async def test_demo_query_strings_are_valid_cypher(projection: Neo4jProjection) -> None:
    """EXPLAIN every DEMO_QUERY — Aura validates syntax without scanning data."""
    assert projection.driver
    async with projection.driver.session() as s:
        for name, cypher in DEMO_QUERIES.items():
            params: dict[str, object] = {}
            if "$from_id" in cypher:
                params["from_id"] = "ws5-test:alice"
            if "$to_id" in cypher:
                params["to_id"] = "ws5-test:acme"
            await s.run(f"EXPLAIN {cypher}", params)
            # If EXPLAIN succeeds, the query is at least syntactically valid
            # against the current Aura schema.
            assert name in DEMO_QUERIES
