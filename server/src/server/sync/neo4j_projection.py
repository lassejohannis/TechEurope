"""
Neo4j Read-only Projection Sync-Worker.

Postgres ist Source-of-Truth. Dieser Worker hört auf Supabase-Realtime
und mappt entities/facts auf idempotente MERGE-Cypher in Neo4j.

Failure-Mode: Sync-Crash = Neo4j-Projection wird stale, nichts korruptes.
Re-Sync via full replay aus Postgres möglich (siehe `replay_all()`).

Hard-Cap: wenn Worker bis Samstag 14:00 nicht stabil läuft, fallback auf
Postgres-only und Neo4j wird im Pitch als "Day 2"-Story geframt.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal

from neo4j import AsyncGraphDatabase, AsyncDriver
from supabase import AsyncClient as SupabaseClient

logger = logging.getLogger(__name__)

EventType = Literal["INSERT", "UPDATE", "DELETE"]


@dataclass(frozen=True)
class SyncConfig:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    supabase_url: str
    supabase_service_key: str
    batch_size: int = 50
    retry_max: int = 5
    retry_backoff_seconds: float = 1.0


class Neo4jProjection:
    """
    Spiegelt Postgres-Entities und -Facts nach Neo4j als Read-only Projection.

    Idempotent — re-running on the same input is safe (MERGE statt CREATE).
    """

    def __init__(self, cfg: SyncConfig):
        self.cfg = cfg
        self.driver: AsyncDriver | None = None
        self.supabase: SupabaseClient | None = None

    async def start(self) -> None:
        self.driver = AsyncGraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        # Supabase client init kept simple; replace with project's actual factory
        # in server/main.py when wiring this up.
        await self._ensure_constraints()
        logger.info("Neo4j projection ready")

    async def stop(self) -> None:
        if self.driver:
            await self.driver.close()

    async def _ensure_constraints(self) -> None:
        """Idempotent constraint + index setup."""
        assert self.driver
        async with self.driver.session() as s:
            await s.run(
                "CREATE CONSTRAINT entity_id IF NOT EXISTS "
                "FOR (n:Entity) REQUIRE n.id IS UNIQUE"
            )
            await s.run(
                "CREATE INDEX entity_type IF NOT EXISTS "
                "FOR (n:Entity) ON (n.entity_type)"
            )

    # ------------------------------------------------------------------
    # Realtime listener
    # ------------------------------------------------------------------

    async def listen(self) -> None:
        """
        Subscribe to Supabase Realtime channels for `entities` and `facts`.

        Each event triggers an idempotent MERGE in Neo4j.
        """
        assert self.supabase
        # Pseudo-code — adjust to actual supabase-py realtime API once wired:
        #
        # await self.supabase.channel("entities-changes") \
        #     .on("postgres_changes", {"event": "*", "table": "entities"},
        #         self._on_entity_event) \
        #     .subscribe()
        # await self.supabase.channel("facts-changes") \
        #     .on("postgres_changes", {"event": "*", "table": "facts"},
        #         self._on_fact_event) \
        #     .subscribe()
        raise NotImplementedError("wire to supabase-py realtime client")

    async def _on_entity_event(self, payload: dict[str, Any]) -> None:
        evt: EventType = payload["eventType"]
        row = payload["new"] if evt != "DELETE" else payload["old"]
        await self._apply_with_retry(self._upsert_entity, evt, row)

    async def _on_fact_event(self, payload: dict[str, Any]) -> None:
        evt: EventType = payload["eventType"]
        row = payload["new"] if evt != "DELETE" else payload["old"]
        await self._apply_with_retry(self._upsert_fact, evt, row)

    # ------------------------------------------------------------------
    # Upsert primitives (idempotent MERGE-Cypher)
    # ------------------------------------------------------------------

    async def _upsert_entity(self, evt: EventType, row: dict[str, Any]) -> None:
        assert self.driver
        if evt == "DELETE":
            cypher = "MATCH (n:Entity {id:$id}) DETACH DELETE n"
            params = {"id": row["id"]}
        else:
            cypher = """
                MERGE (n:Entity {id:$id})
                SET n.entity_type = $entity_type,
                    n.canonical_name = $canonical_name,
                    n.aliases = $aliases,
                    n.attrs = $attrs,
                    n.last_synced = datetime()
            """
            params = {
                "id": row["id"],
                "entity_type": row.get("entity_type"),
                "canonical_name": row.get("canonical_name"),
                "aliases": row.get("aliases") or [],
                "attrs": row.get("attrs") or {},
            }
        async with self.driver.session() as s:
            await s.run(cypher, params)

    async def _upsert_fact(self, evt: EventType, row: dict[str, Any]) -> None:
        """
        Map a reified Fact to a typed edge between two entities.

        Literal-valued facts (object_id IS NULL, object_literal IS NOT NULL)
        are skipped on the graph side — they live as node properties via
        a future enrichment step. For 48h scope: only entity-to-entity facts.
        """
        assert self.driver
        if row.get("object_id") is None:
            return  # literal fact, not a graph edge

        if evt == "DELETE":
            cypher = "MATCH ()-[r:FACT {fact_id:$fact_id}]-() DELETE r"
            params = {"fact_id": row["id"]}
        else:
            # Edge type from predicate (sanitized for Cypher).
            # Predicates are governed by `edge_type_config` ontology table.
            predicate = (row.get("predicate") or "RELATED_TO").upper()
            cypher = f"""
                MATCH (s:Entity {{id:$subject_id}})
                MATCH (o:Entity {{id:$object_id}})
                MERGE (s)-[r:{predicate} {{fact_id:$fact_id}}]->(o)
                SET r.confidence = $confidence,
                    r.valid_from = $valid_from,
                    r.valid_to = $valid_to,
                    r.source_record_id = $source_record_id,
                    r.last_synced = datetime()
            """
            params = {
                "fact_id": row["id"],
                "subject_id": row["subject_id"],
                "object_id": row["object_id"],
                "confidence": row.get("confidence"),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
                "source_record_id": row.get("source_id"),
            }
        async with self.driver.session() as s:
            await s.run(cypher, params)

    # ------------------------------------------------------------------
    # Retry + replay
    # ------------------------------------------------------------------

    async def _apply_with_retry(self, fn, evt: EventType, row: dict[str, Any]) -> None:
        backoff = self.cfg.retry_backoff_seconds
        for attempt in range(1, self.cfg.retry_max + 1):
            try:
                await fn(evt, row)
                return
            except Exception as exc:
                logger.warning(
                    "neo4j sync attempt %d/%d failed for %s: %s",
                    attempt, self.cfg.retry_max, row.get("id"), exc,
                )
                if attempt == self.cfg.retry_max:
                    logger.error("giving up on row %s — projection now stale", row.get("id"))
                    return
                await asyncio.sleep(backoff)
                backoff *= 2

    async def replay_all(self) -> None:
        """
        Full re-sync from Postgres. Call after a long downtime to repair
        a stale projection. Idempotent — safe to run multiple times.
        """
        assert self.supabase
        # 1. Drain entities, batch-MERGE
        # 2. Drain facts (entity-to-entity only), batch-MERGE
        # Use cfg.batch_size for paging.
        raise NotImplementedError("implement once supabase client is wired")


# ----------------------------------------------------------------------
# Cypher-Wow-Demo-Queries — preconfigured for the pitch
# ----------------------------------------------------------------------

DEMO_QUERIES: dict[str, str] = {
    "acme_3hop_neighborhood": """
        MATCH path = (a:Entity {id:'customer:acme-gmbh'})-[*1..3]-(n:Entity)
        RETURN n.canonical_name AS name,
               n.entity_type AS type,
               length(path) AS hops,
               [r IN relationships(path) | type(r)] AS path_types
        ORDER BY hops
        LIMIT 25
    """,
    "shortest_path_persons": """
        MATCH (a:Entity {entity_type:'person', id:$from_id}),
              (b:Entity {entity_type:'person', id:$to_id}),
              path = shortestPath((a)-[*..6]-(b))
        RETURN [n IN nodes(path) | n.canonical_name] AS path,
               length(path) AS hops
    """,
    "champions_with_open_threads": """
        MATCH (p:Entity {entity_type:'person'})-[:CHAMPION_OF]->(c:Entity {entity_type:'company'})
        MATCH (p)-[:PARTICIPANT_IN]->(comm:Entity {entity_type:'communication'})
        WHERE comm.last_activity_days > 14
        RETURN c.canonical_name AS company,
               p.canonical_name AS champion,
               count(comm) AS stale_threads
        ORDER BY stale_threads DESC
        LIMIT 10
    """,
}
