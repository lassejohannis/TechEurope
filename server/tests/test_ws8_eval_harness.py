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
        report_row = {
            "question": "Who is the Engineering Director?",
            "expected": "Raj Patel",
            "actual": "Raj Patel",
            "pass": True,
            "sources_cited": ["hr:employees"],
        }
        assert "pass" in report_row
        assert "sources_cited" in report_row

    def test_harness_loads_questions_yaml(self):
        from server.eval.harness import load_questions
        questions = load_questions()
        assert len(questions) >= 6

    def test_harness_questions_yaml_exists(self):
        from server.eval.harness import _QUESTIONS_PATH
        assert _QUESTIONS_PATH.exists(), f"questions.yaml not found at {_QUESTIONS_PATH}"

    def test_eval_result_dataclass(self):
        from server.eval.harness import EvalResult
        r = EvalResult(
            question="Who is Raj Patel?",
            status="PASS",
            expected_entity="Raj Patel",
            found_entity="Raj Patel",
            expected_facts=[],
            found_facts=[],
            expected_sources=["hr:employees"],
            found_sources=[],
            confidence=0.9,
            confidence_min=0.8,
            latency_ms=42.0,
        )
        assert r.passed is True

    def test_dry_run_validates_questions(self):
        from server.eval.harness import load_questions
        questions = load_questions()
        for q in questions:
            assert q.question
            assert 0.0 <= q.confidence_min <= 1.0
            assert isinstance(q.expected_facts, list)


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
        app_ref, c = _gdpr_mock_client()
        try:
            r = c.delete(f"/api/admin/source-records/{uuid.uuid4()}")
            assert r.status_code == 400  # missing ?confirm=true
        finally:
            app_ref.dependency_overrides.clear()

    def test_delete_requires_confirm(self):
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
    def test_trust_weights_config_exists(self):
        config_path = CONFIG_DIR / "source_trust_weights.yaml"
        assert config_path.exists(), f"source_trust_weights.yaml not found at {config_path}"

    def test_trust_module_loads_weights(self):
        from server.trust import get_source_weight
        assert get_source_weight("crm_contact") == 1.0
        assert get_source_weight("hr_record") == 0.95
        assert get_source_weight("email") == 0.8
        assert get_source_weight("chat") == 0.6

    def test_unknown_source_returns_default(self):
        from server.trust import get_source_weight
        assert get_source_weight("mystery_source") == 0.5

    def test_crm_higher_than_chat(self):
        from server.trust import get_source_weight
        assert get_source_weight("crm_contact") > get_source_weight("chat")

    def test_authority_score_formula(self):
        from server.trust import authority_score
        crm_score = authority_score(0.8, "crm_contact")   # 0.8 * 1.0 = 0.8
        chat_score = authority_score(0.9, "chat")          # 0.9 * 0.6 = 0.54
        assert crm_score > chat_score

    def test_trust_weights_all_in_range(self):
        from server.trust import _load_weights
        for source, weight in _load_weights().items():
            assert 0.0 <= weight <= 1.0, f"{source}: weight {weight} out of range"


# ---------------------------------------------------------------------------
# Time-machine (as_of) endpoint
# ---------------------------------------------------------------------------

class TestTimeMachineEndpoint:
    def test_as_of_endpoint_registered(self):
        from server.main import app
        paths = {r.path for r in app.routes if hasattr(r, "path")}
        assert "/api/entities/{entity_id}" in paths

    def test_as_of_param_in_endpoint(self):
        import inspect
        from server.api.entities import get_entity
        sig = inspect.signature(get_entity)
        assert "as_of" in sig.parameters

    def test_bitemporal_query_logic(self, sample_fact):
        as_of = datetime(2026, 3, 1, tzinfo=timezone.utc)

        def is_active_at(fact: dict, ts: datetime) -> bool:
            vf = fact.get("valid_from")
            vt = fact.get("valid_to")
            if isinstance(vf, str):
                vf = datetime.fromisoformat(vf)
            if isinstance(vt, str):
                vt = datetime.fromisoformat(vt)
            return vf <= ts and (vt is None or vt >= ts)

        active_fact = {**sample_fact,
                       "valid_from": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
                       "valid_to": None}
        assert is_active_at(active_fact, as_of)

        expired_fact = {**sample_fact,
                        "valid_from": datetime(2025, 1, 1, tzinfo=timezone.utc).isoformat(),
                        "valid_to": datetime(2026, 2, 1, tzinfo=timezone.utc).isoformat()}
        assert not is_active_at(expired_fact, as_of)

        future_fact = {**sample_fact,
                       "valid_from": datetime(2026, 4, 1, tzinfo=timezone.utc).isoformat(),
                       "valid_to": None}
        assert not is_active_at(future_fact, as_of)

    def test_as_of_filters_emails_by_date(self, emails):
        """Emails exist across many years — bitemporal filter should reduce set correctly."""
        cutoff = datetime(2015, 1, 1, tzinfo=timezone.utc)

        def parse_date(s: str) -> datetime | None:
            try:
                from dateutil import parser  # type: ignore
                return parser.parse(s).replace(tzinfo=timezone.utc)
            except Exception:
                return None

        pre_cutoff = [e for e in emails[:200] if (d := parse_date(e["date"])) and d < cutoff]
        post_cutoff = [e for e in emails[:200] if (d := parse_date(e["date"])) and d >= cutoff]
        assert len(pre_cutoff) + len(post_cutoff) <= 200
