from __future__ import annotations

from typing import Any

from server.config import settings

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
    """Embed text using Gemini gemini-embedding-001 (Matryoshka, Tier A)."""
    text = " ".join(text.lower().split())
    client = get_gemini()
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text,
        config={"output_dimensionality": dimensions},
    )
    return list(response.embeddings[0].values)


# ---------------------------------------------------------------------------
# Temporal helpers
# ---------------------------------------------------------------------------


def supersede_fact(db, old_fact_id: str, new_values: dict[str, Any]) -> str:
    """Close old_fact_id and insert a replacement with new_values. Returns new fact id."""
    import uuid
    from datetime import datetime, timezone

    now_iso = datetime.now(timezone.utc).isoformat()

    old_res = db.table("facts").select("*").eq("id", old_fact_id).single().execute()
    if not old_res.data:
        raise ValueError(f"Fact {old_fact_id} not found")
    old_row = dict(old_res.data)

    db.table("facts").update({"valid_to": now_iso, "status": "superseded"}).eq(
        "id", old_fact_id
    ).execute()

    new_id = str(uuid.uuid4())
    insert_row = {
        k: v
        for k, v in old_row.items()
        if k not in ("id", "valid_to", "status", "superseded_by", "recorded_at")
    }
    insert_row.update({"id": new_id, "valid_from": now_iso, "status": "active", **new_values})

    db.table("facts").insert(insert_row).execute()
    db.table("facts").update({"superseded_by": new_id}).eq("id", old_fact_id).execute()

    return new_id


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
