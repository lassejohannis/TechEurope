"""WS-6: Frontend Core UI — API response shapes for React components."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


def _make_client(entity):
    from server.main import app
    from server.db import get_db
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=[], count=0)
    chain.single.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=entity)))
    for m in ("eq", "is_", "select", "lte", "or_", "ilike", "in_", "limit", "order", "gte", "neq", "delete", "insert", "update"):
        setattr(chain, m, MagicMock(return_value=chain))
    mock.table.return_value = chain
    mock.rpc.return_value = chain
    app.dependency_overrides[get_db] = lambda: mock
    return app, TestClient(app)


@pytest.fixture
def raj_entity(employees):
    raj = next(e for e in employees if e["emp_id"] == "emp_0431")
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, raj["emp_id"])),
        "entity_type": "person",
        "canonical_name": raj["Name"],
        "aliases": [raj["email"], raj["emp_id"]],
        "attrs": {"emp_id": raj["emp_id"], "category": raj["category"]},
    }


class TestEntityCardShape:
    def test_entity_response_has_all_ui_fields(self, raj_entity):
        """EntityCard component needs: id, canonical_name, entity_type, trust_score, facts."""
        from server.models import EntityResponse
        e = EntityResponse(**{k: v for k, v in raj_entity.items()
                               if k in ("id", "entity_type", "canonical_name", "aliases", "attrs")})
        data = e.model_dump()
        for field in ("id", "canonical_name", "entity_type", "trust_score", "facts", "aliases", "attrs"):
            assert field in data

    def test_entity_type_is_string(self, raj_entity):
        from server.models import EntityResponse
        e = EntityResponse(**{k: v for k, v in raj_entity.items()
                               if k in ("id", "entity_type", "canonical_name", "aliases", "attrs")})
        assert isinstance(e.entity_type, str)

    def test_facts_is_list(self, raj_entity):
        from server.models import EntityResponse
        e = EntityResponse(**{k: v for k, v in raj_entity.items()
                               if k in ("id", "entity_type", "canonical_name", "aliases", "attrs")})
        assert isinstance(e.facts, list)


class TestSearchResultShape:
    def test_search_response_has_results_array(self):
        from server.models import SearchResponse, SearchResult, EntityResponse
        entity = EntityResponse(
            id=str(uuid.uuid4()),
            entity_type="person",
            canonical_name="Raj Patel",
        )
        resp = SearchResponse(
            query="Raj Patel",
            results=[SearchResult(entity=entity, score=0.9, match_type="hybrid")],
            total=1,
        )
        data = resp.model_dump()
        assert "results" in data
        assert "query" in data
        assert "total" in data
        assert data["total"] == 1

    def test_search_result_has_score(self):
        from server.models import SearchResult, EntityResponse
        entity = EntityResponse(id=str(uuid.uuid4()), entity_type="person", canonical_name="Test")
        result = SearchResult(entity=entity, score=0.75, match_type="semantic")
        assert 0.0 <= result.score <= 1.0

    def test_match_type_values(self):
        valid_types = {"hybrid", "semantic", "structural"}
        from server.models import SearchResult, EntityResponse
        for mt in valid_types:
            r = SearchResult(
                entity=EntityResponse(id=str(uuid.uuid4()), entity_type="person", canonical_name="X"),
                score=0.5,
                match_type=mt,
            )
            assert r.match_type == mt


class TestVfsNodeShape:
    def test_vfs_node_for_employee(self, employees):
        from server.api.vfs import _entity_to_vfs_node
        emp = employees[0]
        entity = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, emp["emp_id"])),
            "entity_type": "person",
            "canonical_name": emp["Name"],
            "aliases": [emp["email"]],
            "attrs": {"emp_id": emp["emp_id"]},
        }
        node = _entity_to_vfs_node(entity, f"/persons/{emp['Name'].lower().replace(' ', '-')}")
        data = node.model_dump()
        assert "type" in data
        assert "entity_id" in data
        assert "content" in data
        assert data["content"]["canonical_name"] == emp["Name"]

    def test_vfs_list_response_shape(self):
        from server.models import VfsListResponse
        resp = VfsListResponse(
            path="/persons",
            children=[],
            total=0,
        )
        assert resp.path == "/persons"
        assert isinstance(resp.children, list)


class TestProvenanceShape:
    def test_provenance_response_for_email(self, emails):
        from server.models import ProvenanceResponse, FactResponse, SourceReference
        email = emails[0]
        fact = FactResponse(
            id=str(uuid.uuid4()),
            subject_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, email["sender_emp_id"])),
            predicate="sent_email",
            confidence=0.9,
            derivation="connector_ingest",
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=str(uuid.uuid4()),
        )
        sr = SourceReference(system="email", method="connector_ingest", record_id=email["email_id"])
        prov = ProvenanceResponse(fact=fact, source_reference=sr)
        data = prov.model_dump()
        assert "fact" in data
        assert "source_reference" in data
        assert data["source_reference"]["system"] == "email"
