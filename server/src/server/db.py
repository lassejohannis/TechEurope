"""DB + AI client singletons.

Both clients are lazily initialised on first use so that imports never fail
even when env vars are absent (useful for unit tests and dry-run imports).
"""

from __future__ import annotations

import logging
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


# L1 cache: process-local dict (in-memory, fast). Cleared on process restart.
_EMBEDDING_L1: dict[tuple[str, int], tuple[float, ...] | None] = {}


def _embedding_cache_key(normalized: str, dimensions: int) -> str:
    """sha256(dim:normalized) — stable across processes, used as PK in DB cache."""
    import hashlib
    raw = f"{dimensions}:{normalized}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _embedding_l2_get(content_hash: str) -> tuple[float, ...] | None:
    """L2 cache hit: read embedding from `embedding_cache` table.

    Cache misses are silent (return None) — DB issues should never break
    the embedding pipeline. Bumps hit_count for diagnostics.
    """
    try:
        db = get_db()
        res = (
            db.table("embedding_cache")
            .select("embedding")
            .eq("content_hash", content_hash)
            .limit(1)
            .execute()
        )
        if res.data and res.data[0].get("embedding"):
            try:
                db.rpc("embedding_cache_touch", {"p_hash": content_hash}).execute()
            except Exception:
                pass  # touch is best-effort
            raw = res.data[0]["embedding"]
            # pgvector returns a list-of-floats or stringified vector depending
            # on PostgREST version; normalize either shape.
            if isinstance(raw, str):
                raw = [float(x) for x in raw.strip("[]").split(",") if x.strip()]
            return tuple(float(x) for x in raw)
    except Exception as exc:
        logger.debug("embedding_l2 read failed (will fall through to API): %s", exc)
    return None


def _embedding_l2_put(
    content_hash: str, normalized: str, dimensions: int, vector: tuple[float, ...]
) -> None:
    """L2 cache write — best-effort, never raises."""
    try:
        db = get_db()
        db.table("embedding_cache").upsert(
            {
                "content_hash": content_hash,
                "normalized_text": normalized[:500],  # truncate for storage hygiene
                "dimensions": dimensions,
                "embedding": list(vector),
            },
            on_conflict="content_hash",
        ).execute()
    except Exception as exc:
        logger.debug("embedding_l2 write failed: %s", exc)


def _cached_embed(normalized: str, dimensions: int) -> tuple[float, ...] | None:
    """Two-level cached embedding:

    L1 (in-process dict) → L2 (Postgres `embedding_cache` table) → Gemini API.

    Same name across processes (e.g. "Ravi Kumar" in 100s of source records)
    pays the embedding API once total — afterwards every lookup is a DB
    SELECT or in-memory hit.
    """
    if not normalized:
        return None
    k = (normalized, dimensions)
    if k in _EMBEDDING_L1:
        return _EMBEDDING_L1[k]

    content_hash = _embedding_cache_key(normalized, dimensions)
    cached = _embedding_l2_get(content_hash)
    if cached is not None:
        _EMBEDDING_L1[k] = cached
        return cached

    vec = _embed_single(normalized, dimensions)
    if vec is None:
        _EMBEDDING_L1[k] = None
        return None
    result = tuple(vec)
    _EMBEDDING_L1[k] = result
    _embedding_l2_put(content_hash, normalized, dimensions, result)
    return result


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
