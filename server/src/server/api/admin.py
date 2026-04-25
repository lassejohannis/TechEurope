"""Admin endpoints (reload ontologies, GDPR source-delete cascade, Neo4j replay)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request

from server.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/reload-ontologies", status_code=200)
def reload_ontologies(db=Depends(get_db)):
    """Reload YAML ontologies from config/ontologies/ into entity_type_config / edge_type_config."""
    try:
        from server.ontology.loader import load_ontologies  # type: ignore  (WS-0 delivers this)
        from server.vfs_paths import get_type_slug_maps
        loaded = load_ontologies(db)
        get_type_slug_maps.cache_clear()
        return {"status": "ok", "loaded": loaded}
    except ImportError:
        return {"status": "stub", "message": "Ontology loader not yet available (WS-0 pending)"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/projection/replay", status_code=202)
async def trigger_projection_replay(request: Request, background_tasks: BackgroundTasks):
    """Trigger a full Postgres → Neo4j replay in the background.

    Returns 202 immediately; the replay runs asynchronously and can take
    30–120 seconds depending on data volume.
    """
    proj = getattr(request.app.state, "projection", None)
    if proj is None:
        raise HTTPException(
            status_code=503,
            detail="Neo4j projection not active — running Postgres-only mode.",
        )
    background_tasks.add_task(proj.replay_all)
    return {"status": "replay_started", "message": "Full replay running in background."}


@router.get("/projection/health", status_code=200)
async def projection_health(request: Request):
    """Return Neo4j projection health + sync stats."""
    proj = getattr(request.app.state, "projection", None)
    if proj is None:
        return {"status": "down", "reason": "neo4j not configured"}
    return await proj.healthcheck()


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
    ).limit(1).execute()
    if not (sr_res.data or []):
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
