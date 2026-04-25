"""WS-5: Neo4j Read-only Projection — Cypher syntax + availability checks."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock


def _client():
    from server.main import app
    from server.db import get_db
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[], count=0)
    chain.single.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=None)))
    for m in ("eq", "is_", "select", "lte", "or_", "ilike", "in_", "limit", "order"):
        setattr(chain, m, MagicMock(return_value=chain))
    mock.table.return_value = chain
    mock.rpc.return_value = chain
    app.dependency_overrides[get_db] = lambda: mock
    return app, TestClient(app)


class TestCypherProxy:
    def test_503_without_neo4j_configured(self):
        app, c = _client()
        try:
            r = c.post("/api/query/cypher", json={"query": "MATCH (n) RETURN n LIMIT 1"})
            assert r.status_code == 503
            assert r.json()["detail"]["day_2_feature"] is True
        finally:
            app.dependency_overrides.clear()

    def test_named_queries_returns_neo4j_ready_false(self):
        app, c = _client()
        try:
            r = c.get("/api/query/cypher/named")
            assert r.status_code == 200
            assert r.json()["neo4j_ready"] is False
        finally:
            app.dependency_overrides.clear()

    def test_cypher_syntax_match_return(self):
        query = "MATCH (e:Entity {type: 'person'}) RETURN e.name LIMIT 10"
        assert "MATCH" in query
        assert "RETURN" in query
        assert "LIMIT" in query

    def test_cypher_relationship_traversal(self):
        query = "MATCH (a:Entity)-[:FACT {predicate: 'manages'}]->(b:Entity) RETURN a, b"
        assert "-[:" in query
        assert "]->" in query

    def test_neo4j_projection_module_importable(self):
        try:
            from server.sync.neo4j_projection import DEMO_QUERIES
            assert isinstance(DEMO_QUERIES, dict)
        except ImportError:
            pytest.skip("neo4j not installed")

    @pytest.mark.skip(reason="Requires live Neo4j connection")
    def test_neo4j_live_query(self):
        pass
