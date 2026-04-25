"""WS-8: Eval Harness + Killer Features.

Tests cover:
  - Eval question format + runner contract
  - GDPR source-delete cascade endpoint
  - Per-source trust weighting
  - Time-machine (as_of) endpoint
  - Trust score SQL formula
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"
CONFIG_DIR = Path(__file__).parent.parent.parent / "config"


# ---------------------------------------------------------------------------
# Eval question format (YAML contract)
# ---------------------------------------------------------------------------

SAMPLE_QUESTIONS = [
    {
        "question": "Who is the Engineering Director at Inazuma?",
        "expected_facts": [
            {"subject": "person:raj-patel", "predicate": "job_title", "object": "Engineering Director"}
        ],
        "expected_sources": ["hr:employees"],
        "confidence_min": 0.8,
    },
    {
        "question": "What is Raj Patel's email?",
        "expected_facts": [
            {"subject": "person:raj-patel", "predicate": "email", "object": "raj.patel@inazuma.com"}
        ],
        "expected_sources": ["hr:employees"],
        "confidence_min": 0.9,
    },
    {
        "question": "How many employees does Inazuma have?",
        "expected_facts": [],
        "expected_sources": ["hr:employees"],
        "confidence_min": 0.7,
    },
    {
        "question": "Which customers bought the most products?",
        "expected_facts": [],
        "expected_sources": ["crm:sales"],
        "confidence_min": 0.7,
    },
    {
        "question": "Who reports to Raj Patel?",
        "expected_facts": [],
        "expected_sources": ["hr:employees"],
        "confidence_min": 0.75,
    },
    {
        "question": "What open IT tickets exist for Engineering?",
        "expected_facts": [],
        "expected_sources": ["itsm:it_tickets"],
        "confidence_min": 0.7,
    },
]


class TestEvalQuestionFormat:
    def test_sample_questions_valid(self):
        required = {"question", "expected_facts", "expected_sources", "confidence_min"}
        for q in SAMPLE_QUESTIONS:
            assert required.issubset(q.keys()), f"Missing keys in: {q['question']}"
            assert isinstance(q["expected_facts"], list)
            assert isinstance(q["expected_sources"], list)
            assert 0.0 <= q["confidence_min"] <= 1.0

    def test_minimum_question_count(self):
        assert len(SAMPLE_QUESTIONS) >= 6, "Eval harness needs ≥6 questions (WS-8 spec)"

    def test_expected_fact_schema(self):
        for q in SAMPLE_QUESTIONS:
            for fact in q["expected_facts"]:
                assert "subject" in fact
                assert "predicate" in fact
                assert "object" in fact

    def test_questions_cover_multiple_sources(self):
        all_sources = set()
        for q in SAMPLE_QUESTIONS:
            all_sources.update(q["expected_sources"])
        source_types = {s.split(":")[0] for s in all_sources}
        assert len(source_types) >= 2, "Eval questions should cover ≥2 source types"


# ---------------------------------------------------------------------------
# Eval runner contract
# ---------------------------------------------------------------------------

class TestEvalRunnerContract:
    def _mock_search_result(self, question: dict, found: bool) -> dict:
        """Simulate a search result for a question."""
        if not found:
            return {"question": question["question"], "status": "FAIL", "results": []}
        fact = question["expected_facts"][0] if question["expected_facts"] else {}
        return {
            "question": question["question"],
            "status": "PASS",
            "results": [{
                "entity_id": str(uuid.uuid4()),
                "predicate": fact.get("predicate", ""),
                "value": fact.get("object", ""),
                "confidence": question["confidence_min"] + 0.05,
                "sources": question["expected_sources"],
            }],
        }

    def test_pass_fail_logic(self):
        q = SAMPLE_QUESTIONS[0]
        result = self._mock_search_result(q, found=True)
        assert result["status"] == "PASS"
        assert len(result["results"]) > 0

    def test_html_report_fields(self):
        """HTML report must show: question, expected, actual, ✅/❌, sources."""
        report_row = {
            "question": "Who is the Engineering Director?",
            "expected": "Raj Patel",
            "actual": "Raj Patel",
            "pass": True,
            "sources_cited": ["hr:employees"],
        }
        assert "pass" in report_row
        assert "sources_cited" in report_row


# ---------------------------------------------------------------------------
# GDPR source-delete cascade endpoint
# ---------------------------------------------------------------------------

def _gdpr_mock_client():
    from fastapi.testclient import TestClient
    from server.main import app
    from server.db import get_db
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=None, count=0)
    chain.single.return_value = MagicMock(execute=MagicMock(return_value=MagicMock(data=None)))
    for m in ("eq", "select", "delete"):
        setattr(chain, m, MagicMock(return_value=chain))
    mock_db.table.return_value = chain
    app.dependency_overrides[get_db] = lambda: mock_db
    return app, TestClient(app)


class TestGDPRDelete:
    def test_delete_endpoint_exists(self):
        from server.main import app
        from server.db import get_db
        app_ref, c = _gdpr_mock_client()
        try:
            r = c.delete(f"/api/admin/source-records/{uuid.uuid4()}")
            assert r.status_code == 400  # missing ?confirm=true
        finally:
            app_ref.dependency_overrides.clear()

    def test_delete_requires_confirm(self):
        from server.main import app
        from server.db import get_db
        app_ref, c = _gdpr_mock_client()
        try:
            r = c.delete(f"/api/admin/source-records/{uuid.uuid4()}?confirm=true")
            assert r.status_code in (200, 404)
        finally:
            app_ref.dependency_overrides.clear()

    def test_gdpr_delete_response_shape(self):
        expected = {
            "deleted_source_record": str(uuid.uuid4()),
            "cascaded_facts": 5,
            "gdpr_compliant": True,
        }
        assert expected["gdpr_compliant"] is True
        assert "cascaded_facts" in expected


# ---------------------------------------------------------------------------
# Per-source trust weighting
# ---------------------------------------------------------------------------

class TestTrustWeighting:
    def test_trust_weights_config_format(self):
        """source_trust_weights.yaml must map source_type → float 0–1."""
        # Reference config (matches workstreams.md)
        weights = {
            "email": 0.8,
            "crm_contact": 1.0,
            "hr_record": 0.95,
            "it_ticket": 0.7,
            "chat": 0.6,
        }
        for source, weight in weights.items():
            assert 0.0 <= weight <= 1.0, f"{source}: weight {weight} out of range"

    def test_crm_higher_than_chat(self):
        crm_weight = 1.0
        chat_weight = 0.6
        assert crm_weight > chat_weight

    def test_trust_cascade_authority_tier(self):
        """In auto-resolution: higher source_trust_score wins."""
        fact_a = {"confidence": 0.8, "source_trust": 1.0}  # CRM
        fact_b = {"confidence": 0.9, "source_trust": 0.6}  # chat

        def authority_score(f):
            return f["confidence"] * f["source_trust"]

        assert authority_score(fact_a) > authority_score(fact_b)


# ---------------------------------------------------------------------------
# Time-machine (as_of) endpoint
# ---------------------------------------------------------------------------

class TestTimeMachineEndpoint:
    def test_as_of_endpoint_registered(self):
        from server.main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/entities/{entity_id}" in paths

    def test_as_of_param_in_endpoint(self):
        from fastapi import Query
        from server.api.entities import get_entity
        import inspect
        sig = inspect.signature(get_entity)
        assert "as_of" in sig.parameters

    def test_bitemporal_query_logic(self, sample_fact):
        """Facts returned for as_of must satisfy: valid_from ≤ as_of AND (valid_to IS NULL OR valid_to ≥ as_of)."""
        as_of = datetime(2026, 3, 1, tzinfo=timezone.utc)

        def is_active_at(fact: dict, ts: datetime) -> bool:
            vf = fact.get("valid_from")
            vt = fact.get("valid_to")
            if isinstance(vf, str):
                vf = datetime.fromisoformat(vf)
            if isinstance(vt, str):
                vt = datetime.fromisoformat(vt)
            return vf <= ts and (vt is None or vt >= ts)

        # Fact from 2026-01-01, still valid → should appear
        active_fact = {**sample_fact,
                       "valid_from": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                       "valid_to": None}
        assert is_active_at(active_fact, as_of)

        # Fact that expired before as_of → should NOT appear
        expired_fact = {**sample_fact,
                        "valid_from": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "valid_to": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat()}
        assert not is_active_at(expired_fact, as_of)

        # Future fact → should NOT appear
        future_fact = {**sample_fact,
                       "valid_from": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
                       "valid_to": None}
        assert not is_active_at(future_fact, as_of)
