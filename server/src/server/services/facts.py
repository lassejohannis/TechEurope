from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from supabase import Client

from server.services.id import fact_id


def supersede_fact(client: Client, old_fact_id: str, new_fact: Dict[str, Any]) -> Dict[str, Any]:
    """Supersede an existing fact and insert a new one with deterministic ID.

    new_fact must contain at least subject_id, predicate, object, object_type, derived_from, confidence, status.
    Sets valid_from=now() on new_fact, and updates old fact valid_to=now(), superseded_by=new.id.
    Returns the inserted new fact row.
    """
    now = datetime.now(timezone.utc).isoformat()
    # Fetch old to get subject/predicate defaults if needed
    old = client.table("facts").select("*").eq("id", old_fact_id).single().execute().data
    if not old:
        raise ValueError(f"Fact not found: {old_fact_id}")

    subj = new_fact.get("subject_id") or old["subject_id"]
    pred = new_fact.get("predicate") or old["predicate"]
    obj = new_fact.get("object")
    dfrom = new_fact.get("derived_from") or old.get("derived_from") or []
    new_id = new_fact.get("id") or fact_id(subj, pred, obj, dfrom)

    # Close out old fact: set valid_to and mark status as superseded
    client.table("facts").update({
        "valid_to": now,
        "status": "superseded",
        "superseded_by": new_id,
    }).eq("id", old_fact_id).execute()

    # Insert new fact
    new_row = {
        **new_fact,
        "id": new_id,
        "subject_id": subj,
        "predicate": pred,
        "valid_from": now,
    }
    if not new_row.get("status"):
        new_row["status"] = "live"
    res = client.table("facts").upsert(new_row, on_conflict="id").execute()
    return res.data[0] if res.data else new_row
