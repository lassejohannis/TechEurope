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


_EMBEDDING_MODELS = ("gemini-embedding-001", "text-embedding-004")
_COMPANY_SUFFIXES = (
    " inc", " ltd", " limited", " gmbh", " bv", " corp", " corporation",
    " ag", " sa", " s.a.", " llc", " l.l.c.", " co", " co.",
)


def normalize_for_embedding(text: str) -> str:
    """Cheap normalization that gives more lift than picking a fancier model.

    lowercase, strip common company-suffixes, collapse whitespace.
    """
    if not text:
        return ""
    text = text.lower().rstrip(" .,;:!?")
    for suffix in _COMPANY_SUFFIXES:
        if text.endswith(suffix):
            text = text[: -len(suffix)].rstrip(" .,")
            break
    return " ".join(text.split())


def embed_text(text: str, dimensions: int = 768) -> list[float] | None:
    """Embed text using Gemini. Tries newer model first, falls back to legacy.

    Returns None if both models fail (caller should treat as "skip Tier 3").
    """
    if not text:
        return None
    client = get_gemini()
    normalized = normalize_for_embedding(text)
    last_err: Exception | None = None
    for model_id in _EMBEDDING_MODELS:
        for prefix in ("", "models/"):
            try:
                response = client.models.embed_content(
                    model=f"{prefix}{model_id}",
                    contents=normalized,
                    config={"output_dimensionality": dimensions},
                )
                emb = response.embeddings[0]
                vec = list(getattr(emb, "values", None) or emb)
                if len(vec) == dimensions:
                    return vec
            except Exception as exc:
                last_err = exc
                continue
    logger.warning("embed_text exhausted all models for %r: %s", text[:40], last_err)
    return None


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
