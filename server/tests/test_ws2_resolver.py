"""WS-2: Entity Resolver — normalization, hard-ID matching, alias resolution."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


class TestNameNormalization:
    def test_lowercase_strips_whitespace(self):
        name = "  Raj Patel  "
        assert name.strip().lower() == "raj patel"

    def test_canonical_slug_from_name(self):
        name = "Raj Patel"
        slug = name.lower().replace(" ", "-")
        assert slug == "raj-patel"

    def test_email_domain_normalization(self, employees):
        domains = {e["email"].split("@")[1] for e in employees}
        assert "inazuma.com" in domains

    def test_all_employee_emails_same_domain(self, employees):
        for emp in employees:
            assert emp["email"].endswith("@inazuma.com"), \
                f"{emp['Name']} has non-inazuma email: {emp['email']}"


class TestHardIdMatching:
    def test_emp_id_is_unique_identifier(self, employees):
        emp_map = {e["emp_id"]: e for e in employees}
        assert "emp_0431" in emp_map
        assert emp_map["emp_0431"]["Name"] == "Raj Patel"

    def test_emp_id_format_consistent(self, employees):
        for emp in employees:
            assert emp["emp_id"].startswith("emp_"), \
                f"Unexpected emp_id format: {emp['emp_id']}"

    def test_email_lookup_resolves_to_employee(self, employees):
        email_map = {e["email"]: e for e in employees}
        raj = email_map.get("raj.patel@inazuma.com")
        assert raj is not None
        assert raj["emp_id"] == "emp_0431"

    def test_reportee_resolution(self, employees):
        emp_map = {e["emp_id"]: e for e in employees}
        raj = emp_map["emp_0431"]
        for reportee_id in raj.get("reportees", []):
            assert reportee_id in emp_map, f"Reportee {reportee_id} not in employees"


class TestAliasResolution:
    def test_entity_has_multiple_aliases(self, employees):
        raj = next(e for e in employees if e["emp_id"] == "emp_0431")
        aliases = [raj["email"], raj["emp_id"]]
        assert len(aliases) == 2
        assert "raj.patel@inazuma.com" in aliases
        assert "emp_0431" in aliases

    def test_alias_uniqueness_across_employees(self, employees):
        all_emp_ids = [e["emp_id"] for e in employees]
        assert len(all_emp_ids) == len(set(all_emp_ids)), "emp_ids must be unique"
        # Emails may have rare duplicates in the dataset (~6 of 1260)
        all_emails = [e["email"] for e in employees]
        assert len(set(all_emails)) / len(all_emails) >= 0.99


class TestResolutionDecision:
    def test_resolution_decision_model(self):
        from server.models import ResolutionDecision
        decision = ResolutionDecision(
            decision="merge",
            decided_by="human",
            note="Same emp_id found in HR and email",
        )
        assert decision.decision == "merge"

    def test_resolution_response_shape(self):
        from server.models import ResolutionResponse
        resp = ResolutionResponse(
            id=str(uuid.uuid4()),
            entity_id_1=str(uuid.uuid4()),
            entity_id_2=str(uuid.uuid4()),
            status="pending",
        )
        assert resp.status == "pending"
        assert resp.decided_by is None
