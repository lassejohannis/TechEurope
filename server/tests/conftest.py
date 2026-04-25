"""Shared fixtures for all WS tests.

All fixtures load from local data/enterprise-bench/ — no live DB required.
Set SUPABASE_URL + SUPABASE_SERVICE_KEY in .env to enable live-DB tests
(marked with @pytest.mark.live_db).
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# tests/ → server/ → TechEurope/
REPO_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = REPO_ROOT / "data" / "enterprise-bench"

# ---------------------------------------------------------------------------
# Data fixtures (offline — from JSON files)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def employees():
    with open(DATA_DIR / "Human_Resource_Management/Employees/employees.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def emails():
    with open(DATA_DIR / "Enterprise_mail_system/emails.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def clients():
    with open(DATA_DIR / "Business_and_Management/clients.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def vendors():
    with open(DATA_DIR / "Business_and_Management/vendors.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def customers():
    with open(DATA_DIR / "Customer_Relation_Management/customers.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def products():
    with open(DATA_DIR / "Customer_Relation_Management/products.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def sales():
    with open(DATA_DIR / "Customer_Relation_Management/sales.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def conversations():
    with open(DATA_DIR / "Collaboration_tools/conversations.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def it_tickets():
    with open(DATA_DIR / "IT_Service_Management/it_tickets.json") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def tasks():
    with open(DATA_DIR / "tasks.jsonl") as f:
        return [json.loads(line) for line in f]


# ---------------------------------------------------------------------------
# In-memory entity/fact fixtures (no DB needed)
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_entity():
    return {
        "id": str(uuid.uuid4()),
        "entity_type": "person",
        "canonical_name": "Raj Patel",
        "aliases": ["raj.patel@inazuma.com", "emp_0431"],
        "attrs": {
            "emp_id": "emp_0431",
            "email": "raj.patel@inazuma.com",
            "category": "Engineering",
            "vfs_path": "/persons/raj-patel",
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_company():
    return {
        "id": str(uuid.uuid4()),
        "entity_type": "company",
        "canonical_name": "Inazuma",
        "aliases": ["inazuma.com", "Inazuma.co"],
        "attrs": {
            "industry": "Technology",
            "domain": "inazuma.com",
            "vfs_path": "/companies/inazuma",
        },
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "updated_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_source_record():
    return {
        "id": str(uuid.uuid4()),
        "source_type": "email",
        "source_id": "email:4226322d-0ea5-4344-945a-c00172c6a840",
        "event_type": "communication",
        "raw_content": "Ravi Kumar sent email to Rohan Varma about HR Synergy",
        "timestamp": "2012-03-18T06:58:29Z",
        "metadata": {"method": "connector_ingest", "path": "Enterprise_mail_system/emails.json"},
        "content_hash": "sha256:abc123",
        "ingested_at": datetime.now(tz=timezone.utc).isoformat(),
    }


@pytest.fixture
def sample_fact(sample_entity, sample_source_record):
    return {
        "id": str(uuid.uuid4()),
        "subject_id": sample_entity["id"],
        "predicate": "works_at",
        "object_id": str(uuid.uuid4()),
        "object_literal": None,
        "confidence": 0.95,
        "source_id": sample_source_record["id"],
        "derivation": "connector_ingest",
        "valid_from": datetime.now(tz=timezone.utc).isoformat(),
        "valid_to": None,
        "recorded_at": datetime.now(tz=timezone.utc).isoformat(),
        "superseded_by": None,
        "status": "active",
    }


# ---------------------------------------------------------------------------
# Mock DB — returns fixture data, no Supabase connection needed
# ---------------------------------------------------------------------------

def make_mock_db(entity=None, facts=None, trust=None, source_record=None):
    """Build a MagicMock Supabase client that returns specified fixture data."""
    db = MagicMock()

    def chain_returning(data):
        mock = MagicMock()
        mock.execute.return_value = MagicMock(data=data, count=len(data) if isinstance(data, list) else None)
        mock.eq.return_value = mock
        mock.is_.return_value = mock
        mock.lte.return_value = mock
        mock.or_.return_value = mock
        mock.ilike.return_value = mock
        mock.in_.return_value = mock
        mock.limit.return_value = mock
        mock.order.return_value = mock
        mock.gte.return_value = mock
        mock.select.return_value = mock
        mock.single.return_value = MagicMock(
            execute=MagicMock(return_value=MagicMock(data=data[0] if isinstance(data, list) and data else data))
        )
        return mock

    db.table.return_value = chain_returning([entity] if entity else [])
    db.rpc.return_value = chain_returning([])
    return db


@pytest.fixture
def mock_db(sample_entity, sample_fact, sample_source_record):
    return make_mock_db(entity=sample_entity, facts=[sample_fact], source_record=sample_source_record)


# ---------------------------------------------------------------------------
# Neo4j skip helper (WS-5 integration tests)
# ---------------------------------------------------------------------------

def neo4j_creds_or_skip():
    """Return (uri, password) or skip if Neo4j is not configured."""
    import os
    uri = os.getenv("NEO4J_URI", "")
    password = os.getenv("NEO4J_PASSWORD", "")
    if not uri or not password:
        pytest.skip("NEO4J_URI / NEO4J_PASSWORD not set — skipping live Neo4j test")
    return uri, password
