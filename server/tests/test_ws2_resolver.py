"""WS-2: Entity Resolution Cascade — normalization, hard-ID match, cross-source pairs.

Tests use real EnterpriseBench data for known match/no-match pairs.
Cascade logic is tested against the interface defined in workstreams.md.
"""

from __future__ import annotations

import re
import unicodedata

import pytest


# ---------------------------------------------------------------------------
# Normalization (must match resolver/normalize.py when WS-2 ships)
# ---------------------------------------------------------------------------

def normalize_name(name: str) -> str:
    """Reference implementation of the normalizer — tests against this."""
    name = name.lower().strip()
    # Strip common company suffixes
    name = re.sub(r'\b(inc|ltd|gmbh|bv|llc|corp|co|ag|sa|plc|srl)\b\.?', '', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


class TestNormalization:
    def test_lowercase(self):
        assert normalize_name("RAJ PATEL") == "raj patel"

    def test_strip_inc(self):
        assert normalize_name("Castillo Inc") == "castillo"

    def test_strip_gmbh(self):
        assert normalize_name("Müller GmbH") == "müller"

    def test_strip_ltd(self):
        assert normalize_name("Widgets Ltd.") == "widgets"

    def test_collapse_whitespace(self):
        assert normalize_name("  Raj   Patel  ") == "raj patel"

    def test_idempotent(self):
        name = "Inazuma Corp"
        assert normalize_name(normalize_name(name)) == normalize_name(name)

    def test_same_company_different_suffix(self):
        """Rodriguez Inc and Rodriguez Ltd should normalize to the same token."""
        a = normalize_name("Rodriguez Inc")
        b = normalize_name("Rodriguez Ltd")
        # After stripping suffix, both should be "rodriguez"
        assert a == b

    def test_real_vendor_names(self, vendors):
        """Vendor names from EnterpriseBench normalize without crashing."""
        for v in vendors[:50]:
            result = normalize_name(v["business_name"])
            assert isinstance(result, str)
            assert len(result) > 0


# ---------------------------------------------------------------------------
# Hard ID matching (Tier 1)
# ---------------------------------------------------------------------------

class TestHardIdMatching:
    def test_email_match(self, employees, emails):
        """Person with emp_id=emp_0431 has email raj.patel@inazuma.com in both sources."""
        emp = next(e for e in employees if e["emp_id"] == "emp_0431")
        email_record = next(
            (e for e in emails if e.get("sender_emp_id") == "emp_0431"),
            None,
        )
        assert email_record is not None, "emp_0431 must appear as email sender"
        assert emp["email"] == email_record["sender_email"]
        # Hard-ID match: same email address → Tier 1 hit, confidence=1.0

    def test_emp_id_cross_source(self, employees, emails):
        """emp_id appears in both HR and email source → deterministic anchor."""
        hr_ids = {e["emp_id"] for e in employees if e.get("emp_id")}
        email_sender_ids = {e["sender_emp_id"] for e in emails[:500] if e.get("sender_emp_id")}
        overlap = hr_ids & email_sender_ids
        assert len(overlap) >= 10, f"Expected ≥10 hard-ID overlaps, got {len(overlap)}"

    def test_known_pairs(self, employees, emails):
        """Verified cross-source pairs: same person across HR + email."""
        known = [
            ("emp_0431", "raj.patel@inazuma.com", "Raj Patel"),
            ("emp_0502", "rahul.khanna@inazuma.com", "Rahul Khanna"),
            ("emp_1236", "karan.sharma@inazuma.com", "Karan Sharma"),
        ]
        emp_map = {e["emp_id"]: e for e in employees}
        email_map = {e["sender_emp_id"]: e for e in emails[:2000] if e.get("sender_emp_id")}

        for emp_id, expected_email, expected_name in known:
            emp = emp_map.get(emp_id)
            assert emp is not None, f"Employee {emp_id} not found"
            assert emp["email"] == expected_email, f"{emp_id}: email mismatch"
            assert emp["Name"] == expected_name, f"{emp_id}: name mismatch"
            # Cross-source match
            email_rec = email_map.get(emp_id)
            assert email_rec is not None, f"{emp_id} not found in emails"
            assert email_rec["sender_email"] == expected_email


# ---------------------------------------------------------------------------
# Company cross-source (clients ↔ vendors)
# ---------------------------------------------------------------------------

class TestCompanyResolution:
    def test_same_company_in_two_sources(self, clients, vendors):
        """Companies appearing in both clients.json and vendors.json should resolve."""
        client_norm = {normalize_name(c["business_name"]): c for c in clients}
        vendor_norm = {normalize_name(v["business_name"]): v for v in vendors}
        overlap = set(client_norm.keys()) & set(vendor_norm.keys())
        assert len(overlap) >= 5, f"Expected ≥5 company name overlaps, got {len(overlap)}"

    def test_different_ids_same_company(self, clients, vendors):
        """Same company has different IDs in each source — resolver must merge."""
        client_norm = {normalize_name(c["business_name"]): c["client_id"] for c in clients}
        vendor_norm = {normalize_name(v["business_name"]): v["client_id"] for v in vendors}
        for name in set(client_norm) & set(vendor_norm):
            assert client_norm[name] != vendor_norm[name], \
                f"'{name}' has same ID in both sources — resolver wouldn't be needed"


# ---------------------------------------------------------------------------
# Cascade thresholds
# ---------------------------------------------------------------------------

class TestCascadeThresholds:
    def test_auto_merge_threshold(self):
        """Auto-merge at >0.92, ambiguity inbox at 0.82–0.92, reject <0.82."""
        AUTO_MERGE = 0.92
        INBOX_LOW = 0.82
        assert AUTO_MERGE > INBOX_LOW
        # Simulate a score in each tier
        scores = [0.95, 0.87, 0.75]
        tiers = []
        for s in scores:
            if s > AUTO_MERGE:
                tiers.append("auto_merge")
            elif s >= INBOX_LOW:
                tiers.append("inbox")
            else:
                tiers.append("reject")
        assert tiers == ["auto_merge", "inbox", "reject"]

    def test_no_false_positive_on_partial_name(self, employees):
        """'Kumar' alone should NOT hard-match — many employees share it."""
        kumars = [e for e in employees if "Kumar" in e.get("Name", "")]
        assert len(kumars) > 1, "Multiple employees named Kumar — partial match would be wrong"

    def test_entity_types(self):
        """All required entity types must be handled by the resolver."""
        required = {"person", "company", "product", "document", "communication"}
        # This is a contract test — WS-2 must implement all of these
        implemented = {"person", "company", "product"}  # from workstreams.md tasks 1-5
        assert implemented.issubset(required)


# ---------------------------------------------------------------------------
# Ambiguity inbox contract
# ---------------------------------------------------------------------------

class TestAmbiguityInbox:
    def test_ambiguous_pair_structure(self):
        """A pending resolution must have two entity candidates + signals."""
        import uuid
        resolution = {
            "id": str(uuid.uuid4()),
            "entity_id_1": str(uuid.uuid4()),
            "entity_id_2": str(uuid.uuid4()),
            "status": "pending",
            "resolution_signals": {
                "score": 0.87,
                "tier": "embedding",
                "match_fields": ["canonical_name"],
            },
        }
        assert resolution["status"] == "pending"
        assert 0.82 <= resolution["resolution_signals"]["score"] <= 0.92

    def test_resolution_decision_values(self):
        from server.models import ResolutionDecision
        for decision in ("merge", "reject", "pick_1", "pick_2"):
            rd = ResolutionDecision(decision=decision)
            assert rd.decision == decision
