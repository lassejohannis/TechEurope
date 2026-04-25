from __future__ import annotations

from typing import List

from supabase import Client


def mark_needs_refresh(supabase: Client, updated_ids: List[str]) -> int:
    """Mark dependent facts as needs_refresh given updated source_record IDs.

    Tries to use the SQL helper `mark_facts_needs_refresh(updated_source_ids text[])`.
    Falls back to per-id updates if RPC is unavailable.
    Returns number of facts touched (best-effort).
    """
    if not updated_ids:
        return 0
    try:
        res = supabase.rpc("mark_facts_needs_refresh", {"updated_source_ids": updated_ids}).execute()
        data = getattr(res, "data", None)
        if isinstance(data, list) and data and isinstance(data[0], dict) and "count" in data[0]:
            # some PostgREST shapes return [{'count': n}] — normalize
            return int(data[0]["count"])  # type: ignore[arg-type]
        if isinstance(data, int):
            return int(data)
    except Exception:
        # Fallback: per-id contains update
        touched = 0
        for sid in updated_ids:
            try:
                supabase.table("facts").update({"status": "needs_refresh"}).contains("derived_from", [sid]).neq("status", "needs_refresh").execute()
                touched += 1  # approximate
            except Exception:
                continue
        return touched
    return 0

