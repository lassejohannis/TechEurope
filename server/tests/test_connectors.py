"""Tests for all connectors (no DB required)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.connectors.email import EmailConnector
from server.connectors.crm import CRMConnector
from server.connectors.hr import HRConnector
from server.models import SourceRecord, ExtractionStatus

DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "enterprise-bench"


def _requires_data() -> bool:
    return DATA_PATH.exists()


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_email_discover_count():
    ec = EmailConnector()
    records = list(ec.discover(DATA_PATH))
    assert len(records) >= 100, f"Expected >=100 emails, got {len(records)}"


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_email_normalize_schema():
    ec = EmailConnector()
    raw = next(ec.discover(DATA_PATH))
    rec = ec.normalize(raw)
    assert isinstance(rec, SourceRecord)
    assert rec.source_type == "email"
    assert rec.id.startswith("email:")
    assert len(rec.content_hash) == 64  # sha256 hex
    assert rec.extraction_status == ExtractionStatus.pending
    assert isinstance(rec.payload, dict)


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_email_ids_are_stable():
    ec = EmailConnector()
    raws = list(ec.discover(DATA_PATH))[:20]
    ids_first = [ec.normalize(r).id for r in raws]
    ids_second = [ec.normalize(r).id for r in raws]
    assert ids_first == ids_second


# ---------------------------------------------------------------------------
# CRM
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_crm_discover_types():
    crm = CRMConnector()
    types: set[str] = set()
    for raw in crm.discover(DATA_PATH):
        types.add(raw.get("__source_type", ""))
    assert "customer" in types
    assert "product" in types
    assert "sale" in types


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_crm_normalize_per_type():
    crm = CRMConnector()
    for raw in crm.discover(DATA_PATH):
        rec = crm.normalize(raw)
        assert rec.source_type == raw["__source_type"]
        assert rec.id.startswith(rec.source_type + ":")
        assert not rec.id.startswith("__")
        # Ensure __-prefixed keys stripped from payload
        for k in rec.payload:
            assert not k.startswith("__"), f"Leaked key {k!r} in payload"
        break  # one pass is enough


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_crm_no_duplicate_ids():
    crm = CRMConnector()
    ids = [crm.normalize(r).id for r in crm.discover(DATA_PATH)]
    assert len(ids) == len(set(ids)), "Duplicate CRM IDs found"


# ---------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_hr_discover_count():
    hr = HRConnector()
    records = list(hr.discover(DATA_PATH))
    assert len(records) >= 100


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_hr_normalize_schema():
    hr = HRConnector()
    raw = next(hr.discover(DATA_PATH))
    rec = hr.normalize(raw)
    assert rec.source_type == "hr_record"
    assert rec.id.startswith("hr_record:")
    assert len(rec.content_hash) == 64


@pytest.mark.skipif(not _requires_data(), reason="enterprise-bench data not found")
def test_hr_no_duplicate_ids():
    hr = HRConnector()
    ids = [hr.normalize(r).id for r in hr.discover(DATA_PATH)]
    assert len(ids) == len(set(ids)), "Duplicate HR IDs found"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def test_connector_registry_populated():
    from server.connectors import CONNECTOR_REGISTRY
    assert "email" in CONNECTOR_REGISTRY
    assert "crm" in CONNECTOR_REGISTRY
    assert "hr_record" in CONNECTOR_REGISTRY
    assert "invoice_pdf" in CONNECTOR_REGISTRY


def test_get_connector_lookup():
    from server.connectors import get_connector
    assert get_connector("email") is EmailConnector
    assert get_connector("crm") is CRMConnector
    assert get_connector("hr_record") is HRConnector


def test_get_connector_unknown_raises():
    from server.connectors import get_connector
    with pytest.raises(KeyError):
        get_connector("nonexistent_connector")
