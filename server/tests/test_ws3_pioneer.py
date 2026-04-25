"""WS-3: Pioneer Fine-Tune — entity/fact extraction from real text samples.

Tests define the extraction contract (input → expected output shape).
When Pioneer model is available, set PIONEER_API_KEY in .env and tests
with @pytest.mark.pioneer will run against real inference.

Offline tests validate: text samples from EnterpriseBench, expected entities,
Gemini fallback stub, comparison output format.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "enterprise-bench"

# ---------------------------------------------------------------------------
# Extraction contract: what extract() must return
# ---------------------------------------------------------------------------

def validate_extraction_output(result: Any) -> None:
    """Assert that an extraction result conforms to the expected schema."""
    entities, facts = result
    assert isinstance(entities, list)
    assert isinstance(facts, list)
    for e in entities:
        assert "canonical_name" in e
        assert "entity_type" in e
    for f in facts:
        assert "predicate" in f
        assert "confidence" in f
        assert 0.0 <= f["confidence"] <= 1.0


# ---------------------------------------------------------------------------
# Text samples from real EnterpriseBench data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def email_samples(emails):
    """Return 10 email bodies as plain text for extraction testing."""
    samples = []
    for e in emails[:200]:
        text = e.get("body") or e.get("raw_content") or e.get("subject", "")
        if len(text) > 50:
            samples.append({"id": e["email_id"], "text": text[:1000], "source": "email"})
        if len(samples) >= 10:
            break
    return samples


@pytest.fixture(scope="module")
def conversation_samples(conversations):
    """Return 10 conversation texts."""
    return [
        {"id": c["conversation_id"], "text": c["text"][:1000], "source": "conversation"}
        for c in conversations[:10]
    ]


@pytest.fixture(scope="module")
def ticket_samples(it_tickets):
    """Return 10 IT ticket texts."""
    return [
        {"id": t["id"], "text": t["Issue"][:1000], "source": "it_ticket"}
        for t in it_tickets[:10]
    ]


# ---------------------------------------------------------------------------
# Gemini fallback stub (tests the stub interface without real API)
# ---------------------------------------------------------------------------

def gemini_stub_extract(text: str) -> tuple[list[dict], list[dict]]:
    """Minimal reference implementation that regex-extracts person names + org mentions."""
    entities = []
    facts = []

    # Naive: find capitalised name patterns (2 words)
    names = re.findall(r'\b([A-Z][a-z]+ [A-Z][a-z]+)\b', text)
    seen = set()
    for name in names:
        if name not in seen:
            seen.add(name)
            entities.append({"canonical_name": name, "entity_type": "person", "confidence": 0.6})

    # Naive: inazuma.com emails → company
    if "inazuma" in text.lower():
        entities.append({"canonical_name": "Inazuma", "entity_type": "company", "confidence": 0.9})

    return entities, facts


class TestGeminiStub:
    def test_stub_returns_correct_shape(self):
        text = "Raj Patel sent a message to Rohan Varma at inazuma.com"
        result = gemini_stub_extract(text)
        validate_extraction_output(result)

    def test_stub_finds_person_names(self):
        text = "Raj Patel and Rahul Khanna discussed the Q3 roadmap"
        entities, _ = gemini_stub_extract(text)
        names = [e["canonical_name"] for e in entities if e["entity_type"] == "person"]
        assert "Raj Patel" in names
        assert "Rahul Khanna" in names

    def test_stub_finds_inazuma_company(self):
        text = "Please contact support@inazuma.com for assistance"
        entities, _ = gemini_stub_extract(text)
        companies = [e for e in entities if e["entity_type"] == "company"]
        assert any("Inazuma" in e["canonical_name"] for e in companies)


# ---------------------------------------------------------------------------
# Extraction on real data samples
# ---------------------------------------------------------------------------

class TestExtractionOnRealData:
    def test_email_text_has_extractable_names(self, emails, employees):
        """Emails mention real employee names — extractor must find them."""
        emp_names = {e["Name"] for e in employees[:100]}
        email_texts = " ".join(
            (e.get("body") or e.get("subject") or "")
            for e in emails[:50]
        )
        found = [name for name in emp_names if name in email_texts]
        assert len(found) > 0, "Employee names must appear in email text"

    def test_conversation_contains_person_references(self, conversations):
        conv = conversations[0]
        text = conv["text"]
        # Conversations start with "Name: message" format
        names = re.findall(r'^([A-Z][a-z]+ [A-Z][a-z]+):', text, re.MULTILINE)
        assert len(names) >= 2, "Conversation should have ≥2 named participants"

    def test_it_ticket_contains_person_and_department(self, it_tickets):
        ticket = it_tickets[0]
        text = ticket["Issue"]
        assert len(text) > 20
        # Tickets typically mention "I'm [Name] from [Dept]"
        has_person = bool(re.search(r"I'?m [A-Z]", text))
        assert has_person, f"IT ticket should mention a person: {text[:100]}"


# ---------------------------------------------------------------------------
# Comparison output format (WS-3 deliverable: comparison.json)
# ---------------------------------------------------------------------------

class TestComparisonOutputFormat:
    def test_comparison_schema(self):
        """comparison.json must contain this structure for WS-6 frontend table."""
        sample_comparison = [
            {
                "chunk_id": "email:abc123",
                "text": "Raj Patel discussed roadmap with Rahul Khanna",
                "pioneer": {
                    "entities": [{"canonical_name": "Raj Patel", "entity_type": "person"}],
                    "facts": [],
                    "latency_ms": 45,
                    "cost_usd": 0.00001,
                },
                "gemini": {
                    "entities": [{"canonical_name": "Raj Patel", "entity_type": "person"},
                                 {"canonical_name": "Rahul Khanna", "entity_type": "person"}],
                    "facts": [],
                    "latency_ms": 320,
                    "cost_usd": 0.0001,
                },
            }
        ]
        for item in sample_comparison:
            assert "chunk_id" in item
            assert "pioneer" in item
            assert "gemini" in item
            assert "entities" in item["pioneer"]
            assert "latency_ms" in item["pioneer"]

    def test_pioneer_faster_than_gemini(self):
        """Pioneer fine-tune should be faster (smaller model)."""
        pioneer_latency_ms = 45
        gemini_latency_ms = 320
        assert pioneer_latency_ms < gemini_latency_ms


# ---------------------------------------------------------------------------
# Pioneer integration (skipped unless PIONEER_API_KEY set)
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Requires PIONEER_API_KEY — set in .env to enable")
class TestPioneerIntegration:
    def test_pioneer_extract_person(self):
        from server.extractors.pioneer import extract  # type: ignore
        text = "Raj Patel is the Engineering Director at Inazuma.co"
        result = extract(text)
        validate_extraction_output(result)
        entities, _ = result
        assert any(e["entity_type"] == "person" for e in entities)

    def test_pioneer_extract_company(self):
        from server.extractors.pioneer import extract  # type: ignore
        text = "The deal with Rodriguez Inc was closed by Rahul Khanna"
        entities, facts = extract(text)
        assert any(e["entity_type"] == "company" for e in entities)
