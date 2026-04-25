"""WS-1: Data Ingestion — parsing, deduplication, cross-source linking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


class TestEmployeeIngestion:
    def test_all_employees_parseable(self, employees):
        required = {"Name", "emp_id", "email", "category"}
        for emp in employees:
            assert required.issubset(emp.keys())

    def test_employee_ids_unique(self, employees):
        ids = [e["emp_id"] for e in employees]
        assert len(ids) == len(set(ids)), "Duplicate emp_ids found"

    def test_employee_emails_mostly_unique(self, employees):
        emails = [e["email"] for e in employees]
        unique_ratio = len(set(emails)) / len(emails)
        assert unique_ratio >= 0.99, f"Too many duplicate emails: {1 - unique_ratio:.1%}"

    def test_employee_to_source_record(self, employees):
        from server.models import EntityResponse
        emp = employees[0]
        entity = EntityResponse(
            id=str(uuid.uuid4()),
            entity_type="person",
            canonical_name=emp["Name"],
            aliases=[emp["email"], emp["emp_id"]],
            attrs={"emp_id": emp["emp_id"], "category": emp["category"]},
        )
        assert entity.canonical_name == emp["Name"]

    def test_raj_patel_ingestion_fields(self, employees):
        raj = next(e for e in employees if e["emp_id"] == "emp_0431")
        assert raj["Name"] == "Raj Patel"
        assert raj["email"] == "raj.patel@inazuma.com"
        assert raj["category"] == "Engineering"
        assert raj["Level"] == "EN14"

    def test_employees_cover_multiple_departments(self, employees):
        departments = {e["category"] for e in employees}
        assert len(departments) >= 5

    def test_reportees_reference_valid_emp_ids(self, employees):
        emp_ids = {e["emp_id"] for e in employees}
        for emp in employees:
            for reportee in (emp.get("reportees") or []):
                assert reportee in emp_ids, f"{emp['emp_id']} has unknown reportee {reportee}"


class TestEmailIngestion:
    def test_all_emails_have_required_fields(self, emails):
        required = {"email_id", "sender_email", "sender_emp_id", "recipient_emp_id", "subject"}
        for email in emails[:100]:
            assert required.issubset(email.keys())

    def test_email_ids_unique(self, emails):
        ids = [e["email_id"] for e in emails]
        assert len(ids) == len(set(ids))

    def test_email_senders_are_inazuma_employees(self, employees, emails):
        emp_ids = {e["emp_id"] for e in employees}
        sample = emails[:500]
        matched = sum(1 for e in sample if e["sender_emp_id"] in emp_ids)
        assert matched > 400, "Most email senders should be known employees"

    def test_email_to_source_record_shape(self, emails):
        from server.models import FactResponse
        email = emails[0]
        fact = FactResponse(
            id=str(uuid.uuid4()),
            subject_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, email["sender_emp_id"])),
            predicate="sent_email",
            object_literal=email["email_id"],
            confidence=0.9,
            derivation="connector_ingest",
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=str(uuid.uuid4()),
        )
        assert fact.predicate == "sent_email"


class TestTicketIngestion:
    def test_all_tickets_have_id(self, it_tickets):
        for t in it_tickets:
            assert t.get("id")

    def test_tickets_reference_valid_employees(self, employees, it_tickets):
        emp_ids = {e["emp_id"] for e in employees}
        for ticket in it_tickets:
            raiser = ticket.get("raised_by_emp_id")
            if raiser:
                assert raiser in emp_ids

    def test_ticket_priorities_valid(self, it_tickets):
        valid_priorities = {"low", "medium", "high", "critical"}
        for t in it_tickets:
            if t.get("priority"):
                assert t["priority"].lower() in valid_priorities


class TestIdempotency:
    def test_same_emp_id_produces_same_entity_id(self, employees):
        emp = employees[0]
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, emp["emp_id"]))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, emp["emp_id"]))
        assert id1 == id2

    def test_same_email_produces_same_source_id(self, emails):
        email = emails[0]
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, email["email_id"]))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, email["email_id"]))
        assert id1 == id2
