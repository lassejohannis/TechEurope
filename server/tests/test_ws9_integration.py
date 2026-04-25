"""WS-9: Integration + Architecture boundaries."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


class TestPipelineContract:
    def test_source_record_to_fact_pipeline(self, emails, employees):
        """An email can produce a source_record which produces a fact."""
        from server.models import FactResponse
        emp_map = {e["emp_id"]: e for e in employees}
        email = next(e for e in emails if e["sender_emp_id"] in emp_map)

        source_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email["email_id"]))
        subject_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, email["sender_emp_id"]))

        fact = FactResponse(
            id=str(uuid.uuid4()),
            subject_id=subject_id,
            predicate="sent_email",
            object_literal=email["email_id"],
            confidence=0.9,
            derivation="connector_ingest",
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=source_id,
        )
        assert fact.subject_id == subject_id
        assert fact.source_id == source_id

    def test_employee_to_entity_to_vfs_pipeline(self, employees):
        from server.api.vfs import _entity_to_vfs_node
        emp = next(e for e in employees if e["emp_id"] == "emp_0431")
        entity = {
            "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, emp["emp_id"])),
            "entity_type": "person",
            "canonical_name": emp["Name"],
            "aliases": [emp["email"], emp["emp_id"]],
            "attrs": {"emp_id": emp["emp_id"], "category": emp["category"]},
        }
        node = _entity_to_vfs_node(entity, "/persons/raj-patel")
        assert node.entity_id == entity["id"]
        assert node.content["canonical_name"] == "Raj Patel"

    def test_cross_source_entity_consistency(self, employees, emails):
        """An entity built from HR and email data should be consistent."""
        emp = next(e for e in employees if e["emp_id"] == "emp_0431")
        emp_emails = [e for e in emails if e["sender_emp_id"] == "emp_0431"]
        assert len(emp_emails) > 0
        # Email sender matches employee email
        sender_email = emp_emails[0]["sender_email"]
        assert sender_email == emp["email"]


class TestArchitectureBoundaries:
    def test_db_module_has_get_db(self):
        from server.db import get_db
        assert callable(get_db)

    def test_db_module_has_embed_text(self):
        from server.db import embed_text
        assert callable(embed_text)

    def test_models_module_exports_key_types(self):
        from server.models import (
            EntityResponse, FactResponse, SearchRequest,
            SearchResponse, ProposeFactRequest, VfsNode,
        )
        assert all([EntityResponse, FactResponse, SearchRequest,
                    SearchResponse, ProposeFactRequest, VfsNode])

    def test_all_routers_registered(self):
        from server.main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/entities/{entity_id}" in paths
        assert "/api/search" in paths
        assert any("vfs" in p for p in paths)
        assert "/api/admin/source-records/{source_record_id}" in paths

    def test_mcp_mounted(self):
        from server.main import app
        mounts = [r for r in app.routes if hasattr(r, "path") and "/mcp" in getattr(r, "path", "")]
        assert len(mounts) > 0 or any("/mcp" in str(r) for r in app.routes)

    def test_trust_module_importable(self):
        from server.trust import get_source_weight, authority_score
        assert callable(get_source_weight)
        assert callable(authority_score)

    def test_eval_harness_importable(self):
        from server.eval.harness import load_questions, run_eval
        assert callable(load_questions)
        assert callable(run_eval)


class TestDataCoverage:
    def test_all_data_sources_present(self):
        sources = {
            "HR": DATA_DIR / "Human_Resource_Management/Employees/employees.json",
            "Email": DATA_DIR / "Enterprise_mail_system/emails.json",
            "CRM": DATA_DIR / "Customer_Relation_Management/sales.json",
            "ITSM": DATA_DIR / "IT_Service_Management/it_tickets.json",
            "Collab": DATA_DIR / "Collaboration_tools/conversations.json",
        }
        for name, path in sources.items():
            assert path.exists(), f"Missing {name} data: {path}"

    def test_data_volume_sufficient_for_demo(self, employees, emails, sales):
        assert len(employees) >= 1000
        assert len(emails) >= 10000
        assert len(sales) >= 10000

    @pytest.mark.skip(reason="Requires live Supabase connection")
    def test_live_db_entity_count(self):
        from server.db import get_db
        db = get_db()
        result = db.table("entities").select("id", count="exact").execute()
        assert result.count > 0

    @pytest.mark.skip(reason="Requires live Supabase connection")
    def test_live_db_facts_count(self):
        from server.db import get_db
        db = get_db()
        result = db.table("facts").select("id", count="exact").execute()
        assert result.count > 0
