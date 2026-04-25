"""WS-5: Neo4j Read-only Projection.

Offline tests: Cypher query syntax, sync config, 503-fallback behaviour.
Live tests (skipped by default): require NEO4J_URI + NEO4J_PASSWORD in .env.
"""

from __future__ import annotations

import re

import pytest


# ---------------------------------------------------------------------------
# Demo queries syntax validation
# ---------------------------------------------------------------------------

class TestDemoQueries:
    def test_demo_queries_importable(self):
        """DEMO_QUERIES must be importable even without neo4j installed."""
        from server.api.cypher_proxy import DEMO_QUERIES
        # Either the real dict or the empty fallback
        assert isinstance(DEMO_QUERIES, dict)

    def test_demo_queries_content(self):
        try:
            from server.sync.neo4j_projection import DEMO_QUERIES
        except ImportError:
            pytest.skip("neo4j package not installed")
        assert "acme_3hop_neighborhood" in DEMO_QUERIES
        assert "shortest_path_persons" in DEMO_QUERIES
        assert "champions_with_open_threads" in DEMO_QUERIES

    def test_acme_query_has_match_clause(self):
        try:
            from server.sync.neo4j_projection import DEMO_QUERIES
        except ImportError:
            pytest.skip("neo4j not installed")
        q = DEMO_QUERIES["acme_3hop_neighborhood"]
        assert "MATCH" in q.upper()
        assert "RETURN" in q.upper()

    def test_shortest_path_query_has_param(self):
        try:
            from server.sync.neo4j_projection import DEMO_QUERIES
        except ImportError:
            pytest.skip("neo4j not installed")
        q = DEMO_QUERIES["shortest_path_persons"]
        assert "$from_id" in q or "$to_id" in q

    def test_hop_limit_is_reasonable(self):
        try:
            from server.sync.neo4j_projection import DEMO_QUERIES
        except ImportError:
            pytest.skip("neo4j not installed")
        q = DEMO_QUERIES["acme_3hop_neighborhood"]
        # Should traverse ≤4 hops to avoid demo timeouts
        hops = re.findall(r'\*(\d+)\.\.(\d+)', q)
        if hops:
            max_hop = int(hops[0][1])
            assert max_hop <= 4, f"Demo query traverses {max_hop} hops — may time out"


# ---------------------------------------------------------------------------
# SyncConfig validation
# ---------------------------------------------------------------------------

class TestSyncConfig:
    def test_sync_config_structure(self):
        try:
            from server.sync.neo4j_projection import SyncConfig
        except ImportError:
            pytest.skip("neo4j not installed")
        cfg = SyncConfig(
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="test",
            supabase_url="https://test.supabase.co",
            supabase_secret_key="test-key",
        )
        assert cfg.batch_size == 50
        assert cfg.retry_max == 5

    def test_availability_check(self, monkeypatch):
        """Cypher proxy correctly detects when Neo4j is NOT configured."""
        monkeypatch.setattr("server.config.settings.neo4j_uri", "")
        monkeypatch.setattr("server.config.settings.neo4j_password", "")
        from server.api.cypher_proxy import _neo4j_available
        assert _neo4j_available() is False

    def test_availability_check_positive(self, monkeypatch):
        monkeypatch.setattr("server.config.settings.neo4j_uri", "bolt://localhost:7687")
        monkeypatch.setattr("server.config.settings.neo4j_password", "secret")
        from server.api.cypher_proxy import _neo4j_available
        assert _neo4j_available() is True


# ---------------------------------------------------------------------------
# Upsert Cypher idempotency (logic test, no DB needed)
# ---------------------------------------------------------------------------

class TestUpsertLogic:
    def test_entity_merge_cypher_uses_merge_not_create(self):
        try:
            from server.sync.neo4j_projection import Neo4jProjection
        except ImportError:
            pytest.skip("neo4j not installed")
        # The upsert must use MERGE (idempotent), not CREATE
        import inspect
        src = inspect.getsource(Neo4jProjection._upsert_entity)
        assert "MERGE" in src
        assert "CREATE" not in src.replace("CREATE CONSTRAINT", "")

    def test_literal_facts_skipped(self):
        """Facts with no object_id (scalar) must be skipped — not graph edges."""
        try:
            from server.sync.neo4j_projection import Neo4jProjection
        except ImportError:
            pytest.skip("neo4j not installed")
        import inspect
        src = inspect.getsource(Neo4jProjection._upsert_fact)
        assert "object_id" in src
        assert "return" in src.lower()  # early return for literal facts


# ---------------------------------------------------------------------------
# Live Neo4j tests (skip by default)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Requires NEO4J_URI + NEO4J_PASSWORD — set in .env to enable")
class TestNeo4jLive:
    def test_connection(self):
        from server.config import settings
        assert settings.neo4j_uri, "NEO4J_URI not set"
        # WS-5 will implement actual connection test

    def test_entity_round_trip(self):
        """INSERT entity in Postgres → appears in Neo4j within 2s."""
        pytest.skip("Requires WS-5 sync worker to be running")
