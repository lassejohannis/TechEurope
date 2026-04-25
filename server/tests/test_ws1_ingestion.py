"""WS-1: Ingestion Pipeline — data parsing, idempotency, connector contracts.

All tests run offline against local enterprise-bench files.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import uuid
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


# ---------------------------------------------------------------------------
# Helper: normalise raw row → SourceRecord-like dict (connector contract)
# ---------------------------------------------------------------------------

def to_source_record(source_type: str, source_id: str, raw: dict | str) -> dict:
    content = raw if isinstance(raw, str) else json.dumps(raw, default=str)
    content_hash = "sha256:" + hashlib.sha256(content.encode()).hexdigest()
    return {
        "source_type": source_type,
        "source_id": f"{source_type}:{source_id}",
        "event_type": "ingest",
        "raw_content": content,
        "content_hash": content_hash,
        "metadata": {"source_type": source_type},
    }


def compute_id(source_type: str, source_id: str, content: str) -> str:
    """Deterministic ID: sha256(source_type + source_id + content)."""
    h = hashlib.sha256(f"{source_type}:{source_id}:{content}".encode()).hexdigest()
    return f"{source_type}:sha256:{h[:16]}"


# ---------------------------------------------------------------------------
# Email connector
# ---------------------------------------------------------------------------

class TestEmailConnector:
    def test_emails_file_exists(self):
        assert (DATA_DIR / "Enterprise_mail_system/emails.json").exists()

    def test_emails_parse(self, emails):
        assert len(emails) > 100
        email = emails[0]
        assert "email_id" in email
        assert "sender_email" in email
        assert "sender_name" in email
        assert "recipient_email" in email
        assert "raw_content" in email or "subject" in email  # at least one content field

    def test_email_to_source_record(self, emails):
        email = emails[0]
        sr = to_source_record("email", email["email_id"], email)
        assert sr["source_type"] == "email"
        assert sr["content_hash"].startswith("sha256:")
        assert "email_id" in sr["raw_content"]

    def test_email_idempotent_id(self, emails):
        email = emails[0]
        content = json.dumps(email, default=str)
        id1 = compute_id("email", email["email_id"], content)
        id2 = compute_id("email", email["email_id"], content)
        assert id1 == id2, "Same input must produce same ID"

    def test_email_different_records_different_ids(self, emails):
        e1, e2 = emails[0], emails[1]
        id1 = compute_id("email", e1["email_id"], json.dumps(e1))
        id2 = compute_id("email", e2["email_id"], json.dumps(e2))
        assert id1 != id2

    def test_email_has_thread_id(self, emails):
        """Emails are grouped into threads — important for Communication entities."""
        threaded = [e for e in emails if e.get("thread_id")]
        assert len(threaded) > 0, "At least some emails should have thread_id"

    def test_email_sender_emp_id(self, emails):
        """Sender emp_id links email to employee → cross-source resolution anchor."""
        with_emp = [e for e in emails if e.get("sender_emp_id")]
        assert len(with_emp) / len(emails) > 0.5, "Most emails should have sender_emp_id"


# ---------------------------------------------------------------------------
# CRM / clients connector
# ---------------------------------------------------------------------------

class TestCRMConnector:
    def test_clients_file_exists(self):
        assert (DATA_DIR / "Business_and_Management/clients.json").exists()

    def test_clients_parse(self, clients):
        assert len(clients) > 10
        c = clients[0]
        assert "client_id" in c
        assert "business_name" in c

    def test_clients_have_contact_person(self, clients):
        with_contact = [c for c in clients if c.get("contact_person_name") or c.get("contact_person_id")]
        assert len(with_contact) > 0

    def test_client_to_source_record(self, clients):
        c = clients[0]
        sr = to_source_record("crm_client", c["client_id"], c)
        assert sr["source_type"] == "crm_client"
        assert sr["source_id"] == f"crm_client:{c['client_id']}"

    def test_vendors_file_exists(self):
        assert (DATA_DIR / "Business_and_Management/vendors.json").exists()

    def test_cross_source_same_company_name(self, clients, vendors):
        """11 companies appear in both clients and vendors — key resolution pairs."""
        client_names = {c["business_name"].lower() for c in clients}
        vendor_names = {v["business_name"].lower() for v in vendors}
        overlap = client_names & vendor_names
        assert len(overlap) >= 5, f"Expected ≥5 cross-source company matches, got {len(overlap)}"


# ---------------------------------------------------------------------------
# HR / employees connector
# ---------------------------------------------------------------------------

class TestEmployeeConnector:
    def test_employees_file_exists(self):
        assert (DATA_DIR / "Human_Resource_Management/Employees/employees.json").exists()

    def test_employees_parse(self, employees):
        assert len(employees) > 100
        e = employees[0]
        assert "emp_id" in e
        assert "Name" in e
        assert "email" in e

    def test_employee_email_format(self, employees):
        email_re = re.compile(r"[^@]+@[^@]+\.[^@]+")
        for emp in employees[:50]:
            if emp.get("email"):
                assert email_re.match(emp["email"]), f"Bad email: {emp['email']}"

    def test_employee_reports_to_linkage(self, employees):
        """reports_to field creates Person→Person manages edges."""
        with_reports = [e for e in employees if e.get("reports_to")]
        assert len(with_reports) > 0


# ---------------------------------------------------------------------------
# CSV connector (resume)
# ---------------------------------------------------------------------------

class TestCSVConnector:
    def test_resume_csv_exists(self):
        assert (DATA_DIR / "Human_Resource_Management/Resume/resume_information.csv").exists()

    def test_resume_csv_parse(self):
        path = DATA_DIR / "Human_Resource_Management/Resume/resume_information.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) > 0
        assert "emp_id" in rows[0]
        assert "name" in rows[0] or "Name" in rows[0] or "content" in rows[0]

    def test_resume_csv_links_to_employee(self, employees):
        path = DATA_DIR / "Human_Resource_Management/Resume/resume_information.csv"
        with open(path) as f:
            reader = csv.DictReader(f)
            resume_emp_ids = {row["emp_id"] for row in reader if row.get("emp_id")}
        emp_ids = {e["emp_id"] for e in employees if e.get("emp_id")}
        overlap = resume_emp_ids & emp_ids
        assert len(overlap) > 0, "Resume CSV emp_ids must overlap with employees"


# ---------------------------------------------------------------------------
# Multi-format: JSON, JSONL, CSV coverage
# ---------------------------------------------------------------------------

class TestMultiFormatCoverage:
    def test_jsonl_tasks_file(self, tasks):
        assert len(tasks) > 100
        assert "messages" in tasks[0]

    def test_pdf_files_exist(self):
        pdfs = list((DATA_DIR / "Customer_Relation_Management/Customer_orders").glob("*.pdf"))
        assert len(pdfs) > 10, "Invoice PDFs must be present for PDF adapter test"

    def test_content_hash_changes_on_update(self):
        """Simulates re-ingest: changed content must produce different hash → needs_refresh."""
        original = json.dumps({"value": "old"})
        updated = json.dumps({"value": "new"})
        h1 = hashlib.sha256(original.encode()).hexdigest()
        h2 = hashlib.sha256(updated.encode()).hexdigest()
        assert h1 != h2, "Updated content must change content_hash"
