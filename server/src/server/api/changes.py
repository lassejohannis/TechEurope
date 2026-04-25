"""Recent changes feed — surface fact_changes audit trail."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from server.db import get_supabase

router = APIRouter(prefix="/api/changes", tags=["changes"])


@router.get("/recent")
def recent_changes(limit: int = 50) -> dict[str, Any]:
    """Most recent fact_changes rows from the audit trigger."""
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    db = get_supabase()
    res = (
        db.table("fact_changes")
        .select("id, kind, fact_id, old_value, new_value, triggered_by, at")
        .order("at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = res.data or []
    return {"changes": rows, "total": len(rows)}
