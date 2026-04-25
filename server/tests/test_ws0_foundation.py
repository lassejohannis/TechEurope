"""WS-0: Foundation — models, config, schema contracts."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


class TestPydanticModels:
    def test_entity_response_defaults(self):
        from server.models import EntityResponse
        e = EntityResponse(
            id=str(uuid.uuid4()),
            entity_type="person",
            canonical_name="Raj Patel",
            aliases=[],
            attrs={},
        )
        assert e.trust_score == 0.0
        assert e.fact_count == 0
        assert e.source_diversity == 0
        assert e.facts == []

    def test_fact_response_required_fields(self, sample_fact, sample_entity):
        from server.models import FactResponse
        f = FactResponse(
            id=sample_fact["id"],
            subject_id=sample_entity["id"],
            predicate="works_at",
            confidence=0.95,
            derivation="connector_ingest",
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=sample_fact["source_id"],
        )
        assert f.predicate == "works_at"
        assert f.valid_to is None

    def test_search_request_defaults(self):
        from server.models import SearchRequest
        req = SearchRequest(query="Raj Patel")
        assert req.k == 10
        assert req.entity_type is None
        assert req.as_of is None

    def test_search_result_shape(self):
        from server.models import SearchResult, EntityResponse
        entity = EntityResponse(
            id=str(uuid.uuid4()),
            entity_type="person",
            canonical_name="Raj Patel",
        )
        result = SearchResult(entity=entity, score=0.87, match_type="hybrid")
        assert result.score == 0.87

    def test_source_reference(self):
        from server.models import SourceReference
        sr = SourceReference(system="email", method="connector_ingest", record_id="abc123")
        assert sr.system == "email"

    def test_propose_fact_request(self):
        from server.models import ProposeFactRequest
        req = ProposeFactRequest(
            subject_id=str(uuid.uuid4()),
            predicate="works_at",
            object_id=str(uuid.uuid4()),
            confidence=0.9,
        )
        assert req.source_method == "human_input"

    def test_evidence_item(self):
        from server.models import EvidenceItem
        e = EvidenceItem(source="email", record_id="abc", confidence=0.8)
        assert e.confidence == 0.8

    def test_change_event_model(self):
        from server.models import ChangeEvent
        ce = ChangeEvent(
            event_id=str(uuid.uuid4()),
            event_type="fact_created",
            entity_id=str(uuid.uuid4()),
            fact_id=str(uuid.uuid4()),
            timestamp=datetime.now(tz=timezone.utc),
        )
        assert ce.event_type == "fact_created"


class TestConfig:
    def test_settings_importable(self):
        from server.config import settings
        assert settings is not None

    def test_settings_has_required_fields(self):
        from server.config import settings
        assert hasattr(settings, "supabase_url")
        assert hasattr(settings, "supabase_secret_key")
        assert hasattr(settings, "api_host")
        assert hasattr(settings, "api_port")

    def test_settings_neo4j_defaults(self):
        from server.config import settings
        assert hasattr(settings, "neo4j_uri")
        assert settings.neo4j_uri == "" or isinstance(settings.neo4j_uri, str)


class TestSchemaMigrations:
    def test_trust_view_migration_exists(self):
        migration = Path(__file__).parent.parent / "migrations" / "002_trust_view.sql"
        assert migration.exists()

    def test_trust_view_migration_has_view(self):
        migration = Path(__file__).parent.parent / "migrations" / "002_trust_view.sql"
        sql = migration.read_text()
        assert "entity_trust" in sql
        assert "match_entities" in sql

class TestDataFiles:
    def test_employees_file_exists(self):
        assert (DATA_DIR / "Human_Resource_Management/Employees/employees.json").exists()

    def test_emails_file_exists(self):
        assert (DATA_DIR / "Enterprise_mail_system/emails.json").exists()

    def test_all_required_data_dirs_exist(self):
        required = [
            "Human_Resource_Management/Employees",
            "Enterprise_mail_system",
            "Business_and_Management",
            "Customer_Relation_Management",
            "Collaboration_tools",
            "IT_Service_Management",
        ]
        for d in required:
            assert (DATA_DIR / d).exists(), f"Missing data dir: {d}"
