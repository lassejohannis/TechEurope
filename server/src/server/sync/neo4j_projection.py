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
import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from neo4j import AsyncDriver, AsyncGraphDatabase
from supabase import AsyncClient as SupabaseClient
from supabase import acreate_client

logger = logging.getLogger(__name__)

EventType = Literal["INSERT", "UPDATE", "DELETE"]


@dataclass(frozen=True)
class SyncConfig:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    supabase_url: str
    supabase_secret_key: str
    neo4j_database: str = "neo4j"
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
        self._loop: asyncio.AbstractEventLoop | None = None
        self._channels: list[Any] = []

    async def start(self) -> None:
        self.driver = AsyncGraphDatabase.driver(
            self.cfg.neo4j_uri,
            auth=(self.cfg.neo4j_user, self.cfg.neo4j_password),
        )
        if self.cfg.supabase_url and self.cfg.supabase_secret_key:
            self.supabase = await acreate_client(
                self.cfg.supabase_url,
                self.cfg.supabase_secret_key,
            )
        self._loop = asyncio.get_running_loop()
        await self._ensure_constraints()
        logger.info("Neo4j projection ready")

    async def stop(self) -> None:
        for ch in self._channels:
            try:
                await ch.unsubscribe()
            except Exception as exc:
                logger.warning("channel unsubscribe failed: %s", exc)
        self._channels.clear()
        if self.driver:
            await self.driver.close()

    async def healthcheck(self) -> dict[str, Any]:
        """Cheap probe used by `/query/cypher/_health`."""
        if not self.driver:
            return {"status": "down", "reason": "driver not started"}
        try:
            async with self.driver.session(database=self.cfg.neo4j_database) as s:
                rec = await (await s.run("RETURN 1 AS ok")).single()
                return {"status": "up", "ok": rec["ok"] if rec else None}
        except Exception as exc:
            return {"status": "down", "reason": str(exc)}

    async def _ensure_constraints(self) -> None:
        """Idempotent constraint + index setup."""
        assert self.driver
        async with self.driver.session(database=self.cfg.neo4j_database) as s:
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
        Subscribe to Supabase Realtime on `entities` and `facts`.

        Each event is dispatched to an idempotent MERGE in Neo4j. Returns once
        both channels are subscribed; the supabase-py async client keeps the
        websockets running in its own background tasks.
        """
        assert self.supabase, "call start() first"

        ch_entities = (
            self.supabase.channel("ws5-entities")
            .on_postgres_changes(
                event="*",
                schema="public",
                table="entities",
                callback=lambda p: self._dispatch(self._on_entity_event, p),
            )
        )
        await ch_entities.subscribe()
        self._channels.append(ch_entities)

        ch_facts = (
            self.supabase.channel("ws5-facts")
            .on_postgres_changes(
                event="*",
                schema="public",
                table="facts",
                callback=lambda p: self._dispatch(self._on_fact_event, p),
            )
        )
        await ch_facts.subscribe()
        self._channels.append(ch_facts)

        logger.info("Neo4j projection listening on entities + facts")

    def _dispatch(self, async_handler, payload: dict[str, Any]) -> None:
        """Bridge the sync supabase-py callback into the asyncio loop."""
        if self._loop is None:
            logger.error("event received before loop captured; dropping")
            return
        asyncio.run_coroutine_threadsafe(async_handler(payload), self._loop)

    async def _on_entity_event(self, payload: dict[str, Any]) -> None:
        evt, row = self._extract_event(payload)
        if row is None:
            return
        await self._apply_with_retry(self._upsert_entity, evt, row)

    async def _on_fact_event(self, payload: dict[str, Any]) -> None:
        evt, row = self._extract_event(payload)
        if row is None:
            return
        await self._apply_with_retry(self._upsert_fact, evt, row)

    @staticmethod
    def _extract_event(payload: dict[str, Any]) -> tuple[EventType, dict[str, Any] | None]:
        """Normalize a supabase-py Realtime payload into (event, row)."""
        data = payload.get("data") or payload  # tolerate either shape
        raw_type = data.get("type") or data.get("eventType")
        evt = str(raw_type).upper().replace("REALTIMEPOSTGRESCHANGESLISTENEVENT.", "")
        if evt not in ("INSERT", "UPDATE", "DELETE"):
            logger.warning("unknown event type: %r", raw_type)
            return "INSERT", None  # safe no-op
        row = data.get("old_record") if evt == "DELETE" else data.get("record")
        return evt, row  # type: ignore[return-value]

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
            # Neo4j node properties must be primitives or arrays of primitives.
            # `attrs` (JSONB in Postgres) is serialized to a JSON string here;
            # consumers deserialize on read.
            params = {
                "id": row["id"],
                "entity_type": row.get("entity_type"),
                "canonical_name": row.get("canonical_name"),
                "aliases": row.get("aliases") or [],
                "attrs": json.dumps(row.get("attrs") or {}),
            }
        async with self.driver.session(database=self.cfg.neo4j_database) as s:
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
        async with self.driver.session(database=self.cfg.neo4j_database) as s:
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
        Full re-sync from Postgres. Idempotent (MERGE) — safe to run on every
        boot to repair a stale projection or bootstrap a fresh Neo4j DB.
        """
        assert self.supabase, "call start() first"
        await self._replay_table("entities", self._upsert_entity)
        await self._replay_table("facts", self._upsert_fact)
        logger.info("Neo4j projection replay complete")

    async def _replay_table(self, table: str, upsert) -> None:
        """Idempotent batch sync from Postgres → Neo4j.

        Tolerates a missing table (PGRST205) so the projection can come up
        before WS-0's migration lands; once the table appears and rows are
        inserted, Realtime events take over from `listen()`.
        """
        from postgrest.exceptions import APIError

        assert self.supabase
        offset = 0
        size = self.cfg.batch_size
        total = 0
        while True:
            try:
                res = (
                    await self.supabase.table(table)
                    .select("*")
                    .range(offset, offset + size - 1)
                    .execute()
                )
            except APIError as exc:
                if getattr(exc, "code", None) == "PGRST205":
                    logger.warning(
                        "table %r not found yet — skipping replay; listen() will pick "
                        "it up once the schema is applied",
                        table,
                    )
                    return
                raise
            rows = res.data or []
            if not rows:
                break
            for row in rows:
                await self._apply_with_retry(upsert, "INSERT", row)
            total += len(rows)
            if len(rows) < size:
                break
            offset += size
        logger.info("replayed %d rows from %s", total, table)


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
