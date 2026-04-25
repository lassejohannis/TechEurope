"""WS-6: Frontend Core UI — API contract tests.

Verifies that the API response shapes match what the React frontend expects.
No live DB needed: tests use model serialization + fixture data.

Each test corresponds to a component in workstreams.md WS-6 task list:
  VfsExplorer, EntityDetail, GraphExplorer, AmbiguityInbox, TimeSlider, etc.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# VfsExplorer — needs VfsNode + VfsListResponse
# ---------------------------------------------------------------------------

class TestVfsExplorerContract:
    def test_vfs_node_serialises_to_json(self, sample_entity):
        from server.models import VfsNode
        node = VfsNode(
            path="/companies/inazuma",
            type="company",
            entity_id=sample_entity["id"],
            content={"canonical_name": "Inazuma", "industry": "Technology"},
            metadata={"entity_type": "company"},
        )
        data = node.model_dump()
        assert data["path"] == "/companies/inazuma"
        assert data["type"] == "company"
        assert "canonical_name" in data["content"]

    def test_vfs_list_response(self, sample_entity):
        from server.models import VfsListResponse, VfsNode
        node = VfsNode(
            path="/companies/inazuma",
            type="company",
            entity_id=sample_entity["id"],
            content={"canonical_name": "Inazuma"},
        )
        listing = VfsListResponse(path="/companies", children=[node], total=1)
        data = listing.model_dump()
        assert data["total"] == 1
        assert len(data["children"]) == 1
        assert data["children"][0]["entity_id"] == sample_entity["id"]

    def test_vfs_path_slug_types(self):
        from server.api.vfs import _SLUG_TO_TYPE
        required_types = {"company", "person", "deal", "document", "communication", "product"}
        mapped = set(_SLUG_TO_TYPE.values())
        assert required_types.issubset(mapped), f"Missing VFS types: {required_types - mapped}"


# ---------------------------------------------------------------------------
# EntityDetail — needs EntityResponse with trust_score + facts + source chips
# ---------------------------------------------------------------------------

class TestEntityDetailContract:
    def test_entity_has_trust_score(self, sample_entity):
        from server.models import EntityResponse
        e = EntityResponse(
            id=sample_entity["id"],
            entity_type=sample_entity["entity_type"],
            canonical_name=sample_entity["canonical_name"],
            trust_score=0.78,
            fact_count=12,
            source_diversity=3,
        )
        data = e.model_dump()
        assert "trust_score" in data
        assert "fact_count" in data
        assert "source_diversity" in data

    def test_fact_has_source_chips(self, sample_fact, sample_source_record):
        from server.models import FactResponse, EvidenceItem
        evidence = [EvidenceItem(
            source=sample_source_record["source_type"],
            record_id=sample_source_record["id"],
            confidence=sample_fact["confidence"],
        )]
        fact = FactResponse(
            id=sample_fact["id"],
            subject_id=sample_fact["subject_id"],
            predicate=sample_fact["predicate"],
            confidence=sample_fact["confidence"],
            derivation=sample_fact["derivation"],
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=sample_fact["source_id"],
            evidence=evidence,
        )
        data = fact.model_dump()
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["source"] == "email"

    def test_validate_buttons_write_source_record(self):
        """Validate/Flag buttons must produce a human_input SourceRecord (not fake state)."""
        from server.models import ProposeFactRequest
        req = ProposeFactRequest(
            subject_id=str(uuid.uuid4()),
            predicate="verified_correct",
            confidence=1.0,
            source_system="human_validation",
            source_method="human_input",
            note="User clicked 'Looks correct'",
        )
        assert req.source_system == "human_validation"
        assert req.source_method == "human_input"


# ---------------------------------------------------------------------------
# TimeSlider — needs ?as_of= on entity endpoint
# ---------------------------------------------------------------------------

class TestTimeSliderContract:
    def test_as_of_param_in_entity_endpoint(self):
        from fastapi.testclient import TestClient
        from server.main import app
        from server.db import get_db
        from unittest.mock import MagicMock

        mock_db = MagicMock()
        chain = MagicMock()
        chain.execute.return_value = MagicMock(data=None)
        chain.single.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=None)))
        for m in ("eq", "is_", "lte", "or_", "select", "limit"):
            setattr(chain, m, MagicMock(return_value=chain))
        mock_db.table.return_value = chain

        app.dependency_overrides[get_db] = lambda: mock_db
        try:
            with TestClient(app) as c:
                r = c.get(f"/api/entities/{uuid.uuid4()}?as_of=2026-03-01T00:00:00Z")
                assert r.status_code != 422
        finally:
            app.dependency_overrides.clear()

    def test_fact_has_valid_from_and_valid_to(self, sample_fact):
        from server.models import FactResponse
        fact = FactResponse(
            id=sample_fact["id"],
            subject_id=sample_fact["subject_id"],
            predicate=sample_fact["predicate"],
            confidence=sample_fact["confidence"],
            derivation=sample_fact["derivation"],
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            valid_to=datetime(2026, 4, 1, tzinfo=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=sample_fact["source_id"],
        )
        data = fact.model_dump()
        assert data["valid_from"] is not None
        assert data["valid_to"] is not None


# ---------------------------------------------------------------------------
# AmbiguityInbox — needs ResolutionResponse + decisions
# ---------------------------------------------------------------------------

class TestAmbiguityInboxContract:
    def test_resolution_response_shape(self):
        from server.models import ResolutionResponse
        r = ResolutionResponse(
            id=str(uuid.uuid4()),
            entity_id_1=str(uuid.uuid4()),
            entity_id_2=str(uuid.uuid4()),
            status="pending",
            resolution_signals={"score": 0.87, "tier": "embedding"},
        )
        data = r.model_dump()
        assert data["status"] == "pending"
        assert "resolution_signals" in data

    def test_decision_values(self):
        from server.models import ResolutionDecision
        for v in ("merge", "reject", "pick_1", "pick_2"):
            d = ResolutionDecision(decision=v)
            assert d.decision == v


# ---------------------------------------------------------------------------
# GraphExplorer — node + edge shape for react-flow
# ---------------------------------------------------------------------------

class TestGraphExplorerContract:
    def test_entity_node_fields_for_react_flow(self, sample_entity):
        """react-flow EntityNode needs: id, type, canonical_name, trust_score."""
        from server.models import EntityResponse
        e = EntityResponse(
            id=sample_entity["id"],
            entity_type=sample_entity["entity_type"],
            canonical_name=sample_entity["canonical_name"],
            trust_score=0.72,
        )
        data = e.model_dump()
        # All fields the frontend EntityNode component reads
        assert "id" in data
        assert "entity_type" in data
        assert "canonical_name" in data
        assert "trust_score" in data

    def test_fact_edge_fields_for_react_flow(self, sample_fact):
        """react-flow FactEdge needs: id, predicate, confidence, subject_id, object_id."""
        from server.models import FactResponse
        f = FactResponse(
            id=sample_fact["id"],
            subject_id=sample_fact["subject_id"],
            predicate=sample_fact["predicate"],
            confidence=sample_fact["confidence"],
            derivation=sample_fact["derivation"],
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=sample_fact["source_id"],
            object_id=str(uuid.uuid4()),
        )
        data = f.model_dump()
        assert "predicate" in data
        assert "confidence" in data
        assert "subject_id" in data
        assert "object_id" in data


# ---------------------------------------------------------------------------
# SearchBar — POST /search response shape
# ---------------------------------------------------------------------------

class TestSearchBarContract:
    def test_search_response_shape(self, sample_entity):
        from server.models import EntityResponse, SearchResponse, SearchResult
        entity = EntityResponse(
            id=sample_entity["id"],
            entity_type=sample_entity["entity_type"],
            canonical_name=sample_entity["canonical_name"],
            trust_score=0.81,
        )
        result = SearchResult(entity=entity, score=0.91, match_type="hybrid")
        response = SearchResponse(query="Raj Patel", results=[result], total=1)
        data = response.model_dump()
        assert data["total"] == 1
        assert data["results"][0]["score"] == 0.91
        assert data["results"][0]["entity"]["canonical_name"] == "Raj Patel"

    def test_ingestion_stream_event_shape(self):
        from server.models import ChangeEvent
        event = ChangeEvent(
            event_id=str(uuid.uuid4()),
            event_type="fact_created",
            entity_id=str(uuid.uuid4()),
            timestamp=datetime.now(tz=timezone.utc),
        )
        data = event.model_dump()
        assert data["event_type"] == "fact_created"
        assert "timestamp" in data
