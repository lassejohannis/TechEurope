"""DB + AI client singletons.

Both clients are lazily initialised on first use so that imports never fail
even when env vars are absent (useful for unit tests and dry-run imports).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from server.config import settings
from server.gemini_budget import gemini_call

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

        key = settings.supabase_secret_key or settings.supabase_service_key
        if not settings.supabase_url or not key:
            raise RuntimeError(
                "Supabase URL/key not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY in server/.env."
            )
        _supabase = create_client(settings.supabase_url, key)
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
_EMBEDDING_BATCH_MAX = 100
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


def _embed_single(normalized: str, dimensions: int) -> list[float] | None:
    """Single-text embed with model+prefix fallback, all under gemini_call."""
    if not normalized:
        return None
    client = get_gemini()
    last_err: Exception | None = None
    for model_id in _EMBEDDING_MODELS:
        for prefix in ("", "models/"):
            full_model = f"{prefix}{model_id}"

            def _do_call(_m=full_model):
                return client.models.embed_content(
                    model=_m,
                    contents=normalized,
                    config={"output_dimensionality": dimensions},
                )

            try:
                response = gemini_call(full_model, _do_call)
                if response is None:
                    # cap/cooldown — don't keep trying other models
                    return None
                emb = response.embeddings[0]
                vec = list(getattr(emb, "values", None) or emb)
                if len(vec) == dimensions:
                    return vec
            except Exception as exc:
                last_err = exc
                continue
    logger.warning("embed_text exhausted all models for %r: %s", normalized[:40], last_err)
    return None


@lru_cache(maxsize=2048)
def _cached_embed(normalized: str, dimensions: int) -> tuple[float, ...] | None:
    """LRU-cached embedding. Tuple to be hashable; converted back at call site."""
    vec = _embed_single(normalized, dimensions)
    return tuple(vec) if vec is not None else None


def embed_text(text: str, dimensions: int = 768) -> list[float] | None:
    """Embed text using Gemini. LRU-cached on the normalized text.

    Returns None if both models fail (caller should treat as "skip Tier 3").
    """
    if not text:
        return None
    normalized = normalize_for_embedding(text)
    cached = _cached_embed(normalized, dimensions)
    return list(cached) if cached is not None else None


def embed_texts(texts: list[str], dimensions: int = 768) -> list[list[float] | None]:
    """Batch embed many texts. Cache-first; misses fall through per-text.

    Returns a list aligned with ``texts``. Items can be None individually if
    the API failed for that slot. Returns all-None when budget is exhausted
    (every per-text call short-circuits via ``gemini_call``).
    """
    if not texts:
        return []
    results: list[list[float] | None] = [None] * len(texts)
    for i, raw in enumerate(texts):
        if not raw:
            continue
        norm = normalize_for_embedding(raw)
        if not norm:
            continue
        vec = _cached_embed(norm, dimensions)
        if vec is not None:
            results[i] = list(vec)
    return results


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
