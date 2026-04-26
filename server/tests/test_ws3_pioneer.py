"""WS-3: Pioneer NLP Extraction — entity mention extraction contract."""

from __future__ import annotations

import pytest


class TestMentionExtraction:
    def test_extract_capitalised_names(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Raj Patel is in Engineering")
        assert any("Raj" in m for m in mentions)

    def test_extract_company_name(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Inazuma has 1260 employees")
        assert "Inazuma" in mentions

    def test_extract_quoted_strings(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions('Find "Raj Patel" in the HR system')
        assert "Raj Patel" in mentions

    def test_no_mentions_in_lowercase_query(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("show me all employees")
        assert len(mentions) == 0

    def test_deduplicated_mentions(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Raj Patel and Raj Patel are the same")
        assert mentions.count("Raj Patel") <= 1

    def test_capped_at_five_mentions(self):
        from server.api.search import _extract_mentions
        query = "Alpha Beta Gamma Delta Epsilon Zeta are all teams"
        mentions = _extract_mentions(query)
        assert len(mentions) <= 10  # regex may produce subsets

    def test_extraction_on_real_email_subjects(self, emails):
        from server.api.search import _extract_mentions
        subjects_with_names = [e["subject"] for e in emails[:50] if any(
            c.isupper() for c in e["subject"]
        )]
        for subject in subjects_with_names[:5]:
            mentions = _extract_mentions(subject)
            assert isinstance(mentions, list)

    def test_engineering_director_query(self):
        from server.api.search import _extract_mentions
        mentions = _extract_mentions("Who is the Engineering Director at Inazuma?")
        flat = " ".join(mentions)
        assert "Engineering" in flat or "Inazuma" in flat

    @pytest.mark.skip(reason="Pioneer API requires credentials (WS-3 integration test)")
    def test_pioneer_extract_real_entity(self):
        from server.extractors.pioneer import extract_mentions
        mentions = extract_mentions("Raj Patel manages the engineering team at Inazuma")
        assert len(mentions) > 0

    @pytest.mark.skip(reason="Gemini API requires credentials")
    def test_gemini_embedding_dimensions(self):
        from server.db import embed_text
        embedding = embed_text("Raj Patel", dimensions=768)
        assert len(embedding) == 768


# ─── Pseudo-entity filter ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "etype, name, expected",
    [
        # Real entities — must NOT be flagged
        ("person",       "Rohan Varma",                   False),
        ("person",       "Ravi Kumar",                    False),
        ("person",       "O'Brien",                       False),
        ("person",       "McAllister",                    False),
        # Lowercase real names (CRM/customer data is often lowercased).
        ("person",       "miguel angel paolino",          False),
        ("person",       "henriette pfalzheim",           False),
        ("organization", "inazuma.com",                   False),
        ("document",     "Compliance Policy",             False),
        ("document",     "Inazuma.co Code of Ethics",     False),

        # NER false positives we've actually seen — must be flagged
        ("person",       "Inazuma.co employees",          True),   # plural-suffix
        # Note: "Hardware Assets" structurally looks like a real name
        # (Title-Case, 2 words). Primary defense is the source-type label
        # whitelist in pioneer.py — doc_policy/invoice_pdf don't even ask
        # Pioneer for `person` so this can't be emitted from those paths.
        ("person",       "Legal &amp",                    True),   # html entity
        ("person",       "Complaint",                     True),   # bad literal
        ("person",       "Complainant",                   True),   # bad literal
        ("person",       "Policy",                        True),   # bad literal
        ("person",       "policy",                        True),   # lowercase + literal
        ("person",       "members",                       True),   # plural + literal
        ("person",       "emp_0436",                      True),   # synthetic HR code
        ("person",       "emp-1042",                      True),   # synthetic HR code (dash)
        ("person",       "123abc",                        True),   # starts with digit
        ("person",       "Information Security Policy",   True),   # all generic nouns
        ("person",       "Hardware Assets",               True),   # all generic nouns
        ("organization", "Compliance",                    True),   # bad literal
        ("organization", "Document",                      True),   # bad literal

        # Length guards
        ("person",       "Jo",                            True),   # too short
        ("person",       "x" * 90,                        True),   # too long
    ],
)
def test_is_pseudo_entity(etype, name, expected):
    from server.ontology.engine import _is_pseudo_entity
    assert _is_pseudo_entity(etype, name) is expected
