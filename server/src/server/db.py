from __future__ import annotations

from supabase import create_client, Client

from server.config import settings

_supabase: Client | None = None


def get_supabase() -> Client:
    """Return a cached Supabase client using service/secret key."""
    global _supabase
    if _supabase is None:
        key = settings.supabase_secret_key or settings.supabase_service_key
        if not settings.supabase_url or not key:
            raise RuntimeError(
                "Supabase URL/key not configured. Set SUPABASE_URL and SUPABASE_SECRET_KEY in server/.env."
            )
        _supabase = create_client(settings.supabase_url, key)
    return _supabase


get_db = get_supabase
