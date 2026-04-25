"""DB + AI client singletons.

Both clients are lazily initialised on first use so that imports never fail
even when env vars are absent (useful for unit tests and dry-run imports).
"""

from __future__ import annotations

import logging
from typing import Any

from server.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supabase (sync client — fine for demo/hackathon scale)
# ---------------------------------------------------------------------------

_supabase = None


def get_db():
    """Return a cached Supabase sync client."""
    global _supabase
    if _supabase is None:
        from supabase import create_client

        if not settings.supabase_url or not settings.supabase_secret_key:
            raise RuntimeError("SUPABASE_URL / SUPABASE_SECRET_KEY not set")
        _supabase = create_client(settings.supabase_url, settings.supabase_secret_key)
    return _supabase


# Alias used by ontology loader, connectors, and CLI scripts.
get_supabase = get_db


# ---------------------------------------------------------------------------
# Gemini (google-genai SDK)
# ---------------------------------------------------------------------------

_gemini = None


def get_gemini():
    """Return a cached Gemini client."""
    global _gemini
    if _gemini is None:
        from google import genai

        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        _gemini = genai.Client(api_key=settings.gemini_api_key)
    return _gemini


def embed_text(text: str, dimensions: int = 768) -> list[float]:
    """Embed text using Gemini text-embedding-004 (Matryoshka, Tier A)."""
    client = get_gemini()
    response = client.models.embed_content(
        model="models/text-embedding-004",
        contents=text,
        config={"output_dimensionality": dimensions},
    )
    return list(response.embeddings[0].values)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def row_to_dict(row: Any) -> dict:
    """Normalise a supabase-py result row to a plain dict."""
    if isinstance(row, dict):
        return row
    if hasattr(row, "__dict__"):
        return row.__dict__
    return dict(row)
