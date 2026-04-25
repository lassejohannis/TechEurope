"""Admin endpoints (reload ontologies, GDPR source-delete cascade)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload-ontologies", status_code=200)
def reload_ontologies(db=Depends(get_db)):
    """Reload YAML ontologies from config/ontologies/ into entity_type_config / edge_type_config."""
    try:
        from server.ontology.loader import load_ontologies  # type: ignore  (WS-0 delivers this)
        loaded = load_ontologies(db)
        return {"status": "ok", "loaded": loaded}
    except ImportError:
        return {"status": "stub", "message": "Ontology loader not yet available (WS-0 pending)"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/source-records/{source_record_id}", status_code=200)
def gdpr_delete_source(source_record_id: str, confirm: bool = False, db=Depends(get_db)):
    """GDPR Source-Delete Cascade: deletes source record + cascades to derived facts.

    Requires ?confirm=true to prevent accidental deletion.
    ON DELETE CASCADE on facts.source_id handles the cascade at DB level (WS-0 migration).
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail="Pass ?confirm=true to execute GDPR deletion. This is irreversible.",
        )

    sr_res = db.table("source_records").select("id, source_type").eq(
        "id", source_record_id
    ).single().execute()
    if not sr_res.data:
        raise HTTPException(status_code=404, detail="Source record not found")

    # Count facts that will cascade
    facts_count_res = db.table("facts").select("id", count="exact").eq(
        "source_id", source_record_id
    ).execute()
    facts_count = facts_count_res.count or 0

    db.table("source_records").delete().eq("id", source_record_id).execute()

    return {
        "deleted_source_record": source_record_id,
        "cascaded_facts": facts_count,
        "gdpr_compliant": True,
    }
