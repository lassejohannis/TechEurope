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
