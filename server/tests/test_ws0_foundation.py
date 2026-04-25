"""WS-0: Foundation — Schema, Models, Config, Migration SQL.

Tests run fully offline. Live-DB tests need SUPABASE_URL set.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"
ONTOLOGIES_DIR = Path(__file__).parent.parent.parent / "config" / "ontologies"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class TestModels:
    def test_entity_response_valid(self):
        from server.models import EntityResponse
        e = EntityResponse(
            id=str(uuid.uuid4()),
            entity_type="person",
            canonical_name="Raj Patel",
        )
        assert e.trust_score == 0.0
        assert e.facts == []

    def test_fact_response_valid(self):
        from server.models import FactResponse
        now = datetime.now(tz=timezone.utc)
        f = FactResponse(
            id=str(uuid.uuid4()),
            subject_id=str(uuid.uuid4()),
            predicate="works_at",
            confidence=0.95,
            derivation="connector_ingest",
            valid_from=now,
            recorded_at=now,
            source_id=str(uuid.uuid4()),
        )
        assert f.valid_to is None
        assert f.object_id is None

    def test_propose_fact_confidence_bounds(self):
        from server.models import ProposeFactRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ProposeFactRequest(subject_id="x", predicate="p", confidence=1.5)
        with pytest.raises(ValidationError):
            ProposeFactRequest(subject_id="x", predicate="p", confidence=-0.1)

    def test_search_request_k_bounds(self):
        from server.models import SearchRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SearchRequest(query="test", k=0)
        with pytest.raises(ValidationError):
            SearchRequest(query="test", k=51)
        req = SearchRequest(query="Raj Patel", k=10)
        assert req.entity_type is None

    def test_vfs_node_minimal(self):
        from server.models import VfsNode
        node = VfsNode(
            path="/companies/inazuma",
            type="company",
            entity_id=str(uuid.uuid4()),
            content={"canonical_name": "Inazuma"},
        )
        assert node.children == []

    def test_source_reference_method_field(self):
        from server.models import SourceReference
        sr = SourceReference(system="email", method="connector_ingest")
        assert sr.method == "connector_ingest"
        assert sr.path is None

    def test_resolution_response(self):
        from server.models import ResolutionResponse
        r = ResolutionResponse(
            id=str(uuid.uuid4()),
            entity_id_1=str(uuid.uuid4()),
            entity_id_2=str(uuid.uuid4()),
            status="pending",
        )
        assert r.decided_at is None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_settings_load(self):
        from server.config import settings
        assert settings.api_port == 8000
        assert "localhost" in settings.api_cors_origins[0]

    def test_settings_defaults(self):
        from server.config import settings
        assert settings.neo4j_user == "neo4j"
        assert settings.gemini_model == "gemini-2.0-flash-exp"

    def test_settings_neo4j_optional(self):
        from server.config import settings
        # neo4j_uri default is empty → correctly signals "not configured"
        if not settings.neo4j_uri:
            assert not settings.neo4j_password or settings.neo4j_password == ""


# ---------------------------------------------------------------------------
# Migration SQL
# ---------------------------------------------------------------------------

class TestMigrationSQL:
    def test_migration_002_exists(self):
        sql_file = MIGRATIONS_DIR / "002_trust_view.sql"
        assert sql_file.exists(), "Migration 002_trust_view.sql missing"

    def test_migration_002_contains_trust_view(self):
        sql = (MIGRATIONS_DIR / "002_trust_view.sql").read_text()
        assert "CREATE OR REPLACE VIEW entity_trust" in sql

    def test_migration_002_contains_knn_function(self):
        sql = (MIGRATIONS_DIR / "002_trust_view.sql").read_text()
        assert "match_entities" in sql
        assert "VECTOR(768)" in sql

    def test_migration_002_contains_provenance_function(self):
        sql = (MIGRATIONS_DIR / "002_trust_view.sql").read_text()
        assert "get_fact_provenance_json" in sql

    def test_migration_002_uses_tstzrange_not_tsrange(self):
        """Guard against silent timezone bugs — must use tstzrange."""
        sql = (MIGRATIONS_DIR / "002_trust_view.sql").read_text()
        # No bare 'tsrange' (without 'tz')
        bare_tsrange = re.findall(r'\btsrange\b', sql)
        assert not bare_tsrange, f"Found bare tsrange (use tstzrange): {bare_tsrange}"

    def test_migration_002_recency_decay_formula(self):
        sql = (MIGRATIONS_DIR / "002_trust_view.sql").read_text()
        assert "EXP(" in sql, "Trust score must include recency decay"


# ---------------------------------------------------------------------------
# DB client (offline: just test import + lazy init)
# ---------------------------------------------------------------------------

class TestDbClient:
    def test_get_db_import(self):
        from server.db import get_db, embed_text, get_gemini
        assert callable(get_db)
        assert callable(embed_text)

    def test_get_db_raises_without_env(self, monkeypatch):
        import server.db as db_module
        db_module._supabase = None
        monkeypatch.setattr("server.config.settings.supabase_url", "")
        monkeypatch.setattr("server.config.settings.supabase_service_key", "")
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            db_module.get_db()
        db_module._supabase = None  # reset

    def test_embed_raises_without_key(self, monkeypatch):
        import server.db as db_module
        db_module._gemini = None
        monkeypatch.setattr("server.config.settings.gemini_api_key", "")
        with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
            db_module.embed_text("test")
        db_module._gemini = None  # reset
