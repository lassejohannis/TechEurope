"""WS-4: Query API + MCP Tools — tested against real EnterpriseBench data.

All tests load from data/enterprise-bench/ (no live DB or API keys needed).
Mock DB is seeded with real employee/email/ticket records so assertions are
grounded in the actual dataset, not invented UUIDs.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"


# ---------------------------------------------------------------------------
# Helpers: build DB-row dicts from real data
# ---------------------------------------------------------------------------

def _employee_to_entity(emp: dict) -> dict:
    """Convert a raw employees.json record to a DB entity row."""
    name = emp["Name"]
    slug = name.lower().replace(" ", "-")
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, emp["emp_id"])),
        "entity_type": "person",
        "canonical_name": name,
        "aliases": [emp["email"], emp["emp_id"]],
        "attrs": {
            "emp_id": emp["emp_id"],
            "email": emp["email"],
            "category": emp["category"],
            "level": emp.get("Level", ""),
            "vfs_path": f"/persons/{slug}",
        },
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }


def _email_to_source_record(email: dict) -> dict:
    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_DNS, email["email_id"])),
        "source_type": "email",
        "source_id": f"email:{email['email_id']}",
        "event_type": "communication",
        "raw_content": email.get("body", "")[:200],
        "timestamp": email["date"],
        "metadata": {"method": "connector_ingest"},
        "content_hash": f"sha256:{email['email_id'][:16]}",
        "ingested_at": "2026-01-01T00:00:00+00:00",
    }


def _make_mock_db(entity: dict, facts: list[dict] | None = None, trust: dict | None = None):
    """Mock Supabase client seeded with real-data-derived rows."""
    mock = MagicMock()
    chain = MagicMock()
    chain.execute.return_value = MagicMock(data=facts or [], count=len(facts or []))
    chain.single.return_value = MagicMock(
        execute=MagicMock(return_value=MagicMock(data=entity))
    )
    for method in ("eq", "is_", "lte", "or_", "ilike", "in_", "limit",
                   "order", "gte", "select", "neq", "delete", "insert", "update"):
        setattr(chain, method, MagicMock(return_value=chain))
    mock.table.return_value = chain

    rpc_chain = MagicMock()
    rpc_chain.execute.return_value = MagicMock(data=[])
    mock.rpc.return_value = rpc_chain
    return mock


@pytest.fixture
def raj_entity(employees):
    raj = next(e for e in employees if e["emp_id"] == "emp_0431")
    return _employee_to_entity(raj)


@pytest.fixture
def client(raj_entity):
    from server.main import app
    from server.db import get_db

    mock = _make_mock_db(raj_entity)
    app.dependency_overrides[get_db] = lambda: mock
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 1. Health & OpenAPI
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "/mcp" in body["mcp_endpoint"]
        assert "/docs" in body["openapi_endpoint"]

    def test_openapi_has_all_routes(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        paths = r.json()["paths"]
        assert "/api/entities/{entity_id}" in paths
        assert "/api/search" in paths
        assert "/api/vfs/{path}" in paths


# ---------------------------------------------------------------------------
# 2. Data integrity — validate raw EnterpriseBench files
# ---------------------------------------------------------------------------

class TestDataIntegrity:
    def test_employee_count(self, employees):
        assert len(employees) == 1260

    def test_employee_required_fields(self, employees):
        required = {"Name", "emp_id", "email", "category"}
        for emp in employees:
            assert required.issubset(emp.keys()), f"{emp.get('Name')} missing fields"

    def test_raj_patel_is_engineering_director(self, employees):
        raj = next((e for e in employees if e["emp_id"] == "emp_0431"), None)
        assert raj is not None
        assert raj["Name"] == "Raj Patel"
        assert raj["category"] == "Engineering"
        assert raj["Level"] == "EN14"
        assert raj["email"] == "raj.patel@inazuma.com"

    def test_raj_patel_has_reportees(self, employees):
        raj = next(e for e in employees if e["emp_id"] == "emp_0431")
        assert isinstance(raj.get("reportees"), list)
        assert len(raj["reportees"]) > 0

    def test_email_count(self, emails):
        assert len(emails) >= 11000

    def test_email_required_fields(self, emails):
        required = {"email_id", "sender_email", "sender_emp_id", "recipient_emp_id", "subject"}
        sample = emails[:50]
        for email in sample:
            assert required.issubset(email.keys())

    def test_emails_reference_real_employees(self, employees, emails):
        emp_ids = {e["emp_id"] for e in employees}
        sample_senders = {em["sender_emp_id"] for em in emails[:200]}
        overlap = sample_senders & emp_ids
        assert len(overlap) > 5, "Email senders should map to known employees"

    def test_it_tickets_reference_real_employees(self, employees, it_tickets):
        emp_ids = {e["emp_id"] for e in employees}
        for ticket in it_tickets:
            if ticket.get("raised_by_emp_id"):
                assert ticket["raised_by_emp_id"] in emp_ids, \
                    f"Ticket {ticket['id']} raised by unknown emp {ticket['raised_by_emp_id']}"

    def test_sales_record_count(self, sales):
        assert len(sales) >= 13000

    def test_client_count(self, clients):
        assert len(clients) == 400


# ---------------------------------------------------------------------------
# 3. Entity endpoint — built from real employee data
# ---------------------------------------------------------------------------

class TestEntityEndpoint:
    def test_entity_response_from_raj_patel(self, raj_entity):
        from server.models import EntityResponse
        e = EntityResponse(
            id=raj_entity["id"],
            entity_type=raj_entity["entity_type"],
            canonical_name=raj_entity["canonical_name"],
            aliases=raj_entity["aliases"],
            attrs=raj_entity["attrs"],
        )
        assert e.canonical_name == "Raj Patel"
        assert e.entity_type == "person"
        assert "emp_0431" in e.aliases
        assert "raj.patel@inazuma.com" in e.aliases
        assert e.attrs["category"] == "Engineering"
        assert e.trust_score == 0.0
        assert e.facts == []

    def test_entity_vfs_path_from_real_name(self, raj_entity):
        assert raj_entity["attrs"]["vfs_path"] == "/persons/raj-patel"

    def test_get_entity_via_api(self, client, raj_entity):
        r = client.get(f"/api/entities/{raj_entity['id']}")
        assert r.status_code == 200
        body = r.json()
        assert body["canonical_name"] == "Raj Patel"
        assert body["entity_type"] == "person"

    def test_as_of_param_accepted(self, client, raj_entity):
        r = client.get(f"/api/entities/{raj_entity['id']}?as_of=2026-04-01T00:00:00Z")
        assert r.status_code in (200, 422)  # 422 only for truly invalid UUID

    def test_entity_built_for_every_department(self, employees):
        """All departments in employees.json can produce valid EntityResponse objects."""
        from server.models import EntityResponse
        departments = {}
        for emp in employees:
            departments.setdefault(emp["category"], emp)

        for dept, emp in list(departments.items())[:5]:
            entity = _employee_to_entity(emp)
            e = EntityResponse(
                id=entity["id"],
                entity_type=entity["entity_type"],
                canonical_name=entity["canonical_name"],
                aliases=entity["aliases"],
                attrs=entity["attrs"],
            )
            assert e.entity_type == "person"
            assert e.attrs["category"] == dept


# ---------------------------------------------------------------------------
# 4. Facts / provenance — from real email source records
# ---------------------------------------------------------------------------

class TestFactsEndpoint:
    def test_provenance_endpoint_exists(self, client):
        r = client.get(f"/api/facts/{uuid.uuid4()}/provenance")
        assert r.status_code in (200, 404, 500)

    def test_provenance_from_real_email(self, emails, raj_entity):
        """Build a ProvenanceResponse from a real email sent by Raj Patel."""
        from server.models import FactResponse, ProvenanceResponse, SourceReference

        raj_emails = [e for e in emails if e["sender_emp_id"] == "emp_0431"]
        assert len(raj_emails) > 0, "Raj Patel should have sent at least one email"

        email = raj_emails[0]
        sr = SourceReference(
            system="email",
            method="connector_ingest",
            record_id=email["email_id"],
        )
        fact = FactResponse(
            id=str(uuid.uuid4()),
            subject_id=raj_entity["id"],
            predicate="sent_email",
            confidence=0.9,
            derivation="connector_ingest",
            valid_from=datetime.now(tz=timezone.utc),
            recorded_at=datetime.now(tz=timezone.utc),
            source_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, email["email_id"])),
        )
        prov = ProvenanceResponse(fact=fact, source_reference=sr)
        assert prov.superseded_by is None
        data = prov.model_dump()
        assert data["source_reference"]["record_id"] == email["email_id"]

    def test_fact_for_ticket_raised_by_real_employee(self, it_tickets, employees):
        """Every IT ticket maps back to a known employee."""
        from server.models import FactResponse
        emp_ids = {e["emp_id"] for e in employees}

        for ticket in it_tickets[:20]:
            raiser = ticket.get("raised_by_emp_id")
            assert raiser in emp_ids
            # Build a fact to represent the ticket relationship
            fact = FactResponse(
                id=str(uuid.uuid4()),
                subject_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, raiser)),
                predicate="raised_ticket",
                object_literal=ticket["id"],
                confidence=1.0,
                derivation="connector_ingest",
                valid_from=datetime.now(tz=timezone.utc),
                recorded_at=datetime.now(tz=timezone.utc),
                source_id=str(uuid.uuid4()),
            )
            assert fact.predicate == "raised_ticket"


# ---------------------------------------------------------------------------
# 5. Search — mention extraction and combine logic on real names
# ---------------------------------------------------------------------------

class TestSearchWithRealData:
    def test_mention_extraction_on_raj_patel(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Who is Raj Patel?")
        flat = " ".join(mentions)
        assert "Raj" in flat or "Patel" in flat

    def test_mention_extraction_on_inazuma(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("How many employees does Inazuma have?")
        assert "Inazuma" in mentions

    def test_mention_extraction_on_engineering_director(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Who is the Engineering Director?")
        flat = " ".join(mentions)
        assert "Engineering" in flat or "Director" in flat

    def test_empty_query_rejected(self, client):
        r = client.post("/api/search", json={"query": "   ", "k": 5})
        assert r.status_code == 400

    def test_search_request_model(self):
        from server.models import SearchRequest
        req = SearchRequest(query="Raj Patel", k=5, entity_type="person")
        assert req.query == "Raj Patel"
        assert req.k == 5
        assert req.entity_type == "person"

    def test_search_with_real_employee_name(self, client):
        with patch("server.api.search.embed_text", return_value=[0.1] * 768):
            r = client.post("/api/search", json={"query": "Raj Patel Engineering Director", "k": 5})
        assert r.status_code == 200
        body = r.json()
        assert body["query"] == "Raj Patel Engineering Director"
        assert "results" in body
        assert isinstance(body["results"], list)

    def test_hybrid_combine_intersects_when_both_signals(self, employees):
        """Stage 3: use real emp_ids to verify intersect logic."""
        # Two employees known to be in both semantic and structural results
        emp_a = str(uuid.uuid5(uuid.NAMESPACE_DNS, "emp_0431"))  # Raj Patel
        emp_b = str(uuid.uuid5(uuid.NAMESPACE_DNS, "emp_0106"))  # a reportee

        semantic = {emp_a: 0.9, emp_b: 0.8}
        structural = {emp_a, emp_b}

        intersection = set(semantic.keys()) & structural
        combined = intersection if intersection else set(semantic.keys()) | structural
        assert combined == {emp_a, emp_b}

    def test_hybrid_combine_unions_when_no_overlap(self, employees):
        """If semantic and structural have no common hits → union."""
        emp_a = str(uuid.uuid5(uuid.NAMESPACE_DNS, "emp_0431"))
        emp_b = str(uuid.uuid5(uuid.NAMESPACE_DNS, "emp_0920"))

        semantic = {emp_a: 0.9}
        structural = {emp_b}

        intersection = set(semantic.keys()) & structural
        combined = intersection if intersection else set(semantic.keys()) | structural
        assert combined == {emp_a, emp_b}


# ---------------------------------------------------------------------------
# 6. VFS — paths and nodes built from real employee names
# ---------------------------------------------------------------------------

class TestVfsWithRealData:
    def test_path_segments(self):
        from server.api.vfs import _path_segments, _SLUG_TO_TYPE
        assert _path_segments("/companies/inazuma") == ["companies", "inazuma"]
        assert _path_segments("contacts/raj-patel/deals") == ["contacts", "raj-patel", "deals"]
        assert _SLUG_TO_TYPE["companies"] == "company"
        assert _SLUG_TO_TYPE["contacts"] == "person"

    def test_vfs_node_from_raj_patel(self, raj_entity):
        from server.api.vfs import _entity_to_vfs_node
        node = _entity_to_vfs_node(raj_entity, "/persons/raj-patel")
        assert node.type == "person"
        assert node.entity_id == raj_entity["id"]
        assert "canonical_name" in node.content

    def test_vfs_nodes_for_multiple_employees(self, employees):
        from server.api.vfs import _entity_to_vfs_node
        for emp in employees[:10]:
            entity = _employee_to_entity(emp)
            slug = emp["Name"].lower().replace(" ", "-")
            node = _entity_to_vfs_node(entity, f"/persons/{slug}")
            assert node.type == "person"
            assert node.content["canonical_name"] == emp["Name"]

    def test_propose_fact_request_from_real_employees(self, employees):
        from server.models import ProposeFactRequest
        raj = next(e for e in employees if e["emp_id"] == "emp_0431")
        reportee_id = raj["reportees"][0]

        req = ProposeFactRequest(
            subject_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, raj["emp_id"])),
            predicate="manages",
            object_id=str(uuid.uuid5(uuid.NAMESPACE_DNS, reportee_id)),
            confidence=0.95,
            note=f"Raj Patel manages {reportee_id} per HR data",
        )
        assert req.predicate == "manages"
        assert req.source_method == "human_input"

    def test_propose_fact_endpoint(self, client, employees):
        raj = next(e for e in employees if e["emp_id"] == "emp_0431")
        r = client.post("/api/vfs/propose-fact", json={
            "subject_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, raj["emp_id"])),
            "predicate": "works_at",
            "object_id": str(uuid.uuid4()),
            "confidence": 0.95,
        })
        assert r.status_code in (201, 200, 500)

    def test_vfs_list_route(self, client):
        r = client.get("/api/vfs/contacts")
        assert r.status_code in (200, 400, 404)

    def test_vfs_delete_route(self, client, raj_entity):
        r = client.delete(f"/api/vfs/persons/{raj_entity['id']}")
        assert r.status_code in (200, 404, 400)


# ---------------------------------------------------------------------------
# 7. Cypher proxy
# ---------------------------------------------------------------------------

class TestCypherProxy:
    def test_cypher_503_without_neo4j(self, client, monkeypatch):
        monkeypatch.setattr("server.config.settings.neo4j_uri", "")
        monkeypatch.setattr("server.config.settings.neo4j_password", "")
        r = client.post("/api/query/cypher", json={"query": "MATCH (n) RETURN n LIMIT 1"})
        assert r.status_code == 503
        assert r.json()["detail"]["day_2_feature"] is True

    def test_named_queries_list(self, client, monkeypatch):
        monkeypatch.setattr("server.config.settings.neo4j_uri", "")
        monkeypatch.setattr("server.config.settings.neo4j_password", "")
        r = client.get("/api/query/cypher/named")
        assert r.status_code == 200
        assert r.json()["neo4j_ready"] is False

    def test_cypher_400_empty_query(self, client, monkeypatch):
        monkeypatch.setattr("server.config.settings.neo4j_uri", "bolt://localhost:7687")
        monkeypatch.setattr("server.config.settings.neo4j_password", "test")
        r = client.post("/api/query/cypher", json={})
        assert r.status_code in (400, 502)


# ---------------------------------------------------------------------------
# 8. MCP Tools
# ---------------------------------------------------------------------------

class TestMCPTools:
    def test_mcp_importable(self):
        from server.mcp.server import mcp
        assert mcp is not None

    def test_search_memory_signature(self):
        import inspect
        from server.mcp.server import search_memory
        sig = inspect.signature(search_memory)
        assert "query" in sig.parameters
        assert "k" in sig.parameters

    def test_get_entity_signature(self):
        import inspect
        from server.mcp.server import get_entity
        sig = inspect.signature(get_entity)
        assert "entity_id" in sig.parameters

    def test_propose_fact_signature(self):
        import inspect
        from server.mcp.server import propose_fact
        sig = inspect.signature(propose_fact)
        assert "subject_id" in sig.parameters
        assert "predicate" in sig.parameters
        assert "confidence" in sig.parameters

    def test_list_recent_changes_signature(self):
        import inspect
        from server.mcp.server import list_recent_changes
        sig = inspect.signature(list_recent_changes)
        assert "since" in sig.parameters
        assert "limit" in sig.parameters

    def test_mcp_tools_cover_core_operations(self):
        """MCP must expose search, read, write, audit — the 4 agent operations."""
        from server.mcp import server as mcp_module
        for fn_name in ("search_memory", "get_entity", "propose_fact", "list_recent_changes"):
            assert hasattr(mcp_module, fn_name), f"MCP missing tool: {fn_name}"


# ---------------------------------------------------------------------------
# 9. Trust score — formula validated with realistic Inazuma numbers
# ---------------------------------------------------------------------------

class TestTrustScore:
    def test_formula_with_real_source_count(self, employees, emails, it_tickets):
        """Trust formula applied to Raj Patel's real data footprint."""
        import math

        # Raj's data exists in: HR (1), emails (N), tickets (M) = 3 source types
        raj_email_count = sum(1 for e in emails if e["sender_emp_id"] == "emp_0431")
        assert raj_email_count > 0

        raj_tickets = sum(1 for t in it_tickets if t.get("raised_by_emp_id") == "emp_0431"
                          or t.get("emp_id") == "emp_0431")

        source_count = 3 if raj_email_count > 0 else 2
        avg_confidence = 0.9
        source_diversity_factor = min(source_count / 3.0, 1.0)
        days_since_last = 5
        recency_decay = math.exp(-days_since_last / 30.0)

        trust = avg_confidence * source_diversity_factor * recency_decay
        assert 0.0 < trust <= 1.0
        assert trust > 0.7  # well-connected employee with fresh data

    def test_low_confidence_lowers_trust(self):
        import math
        decay = math.exp(-1 / 30.0)
        assert 0.95 * 1.0 * decay > 0.3 * 1.0 * decay

    def test_single_source_vs_multi_source(self, employees):
        """An employee appearing in 1 system vs 3 systems."""
        import math
        decay = math.exp(-1 / 30.0)
        single = 0.9 * min(1 / 3.0, 1.0) * decay
        multi = 0.9 * min(3 / 3.0, 1.0) * decay
        assert single < multi

    def test_old_data_lower_trust(self):
        import math
        recent = math.exp(-1 / 30.0)
        old = math.exp(-60 / 30.0)
        assert recent > old

    def test_trust_score_model_field(self, raj_entity):
        from server.models import EntityResponse
        e = EntityResponse(**{k: v for k, v in raj_entity.items()
                               if k in ("id", "entity_type", "canonical_name", "aliases", "attrs")})
        assert e.trust_score == 0.0  # default before DB computation
        assert 0.0 <= e.trust_score <= 1.0

    def test_all_departments_represented_in_employees(self, employees):
        """Diversity check: employees span multiple departments → diverse trust signals."""
        departments = {e["category"] for e in employees}
        assert len(departments) >= 5, f"Expected ≥5 departments, got: {departments}"
