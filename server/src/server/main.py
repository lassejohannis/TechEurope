"""FastAPI app — single process exposing the Query API for both layers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone

from server.config import settings
from server.db import get_supabase
from server.ontology.loader import load_all, upsert_to_db, get_ontology_dir, load_yaml
from server.connectors import CONNECTOR_REGISTRY, get_connector

app = FastAPI(
    title="Tech Europe — Context Engine",
    version="0.1.0",
    description=(
        "Boilerplate for the Big Berlin Hack 2026 (Qontext track). "
        "Day-1 work fills in Core Context Engine endpoints + Revenue App routes."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="tech-europe-server",
        version="0.1.0",
    )


@app.get("/api/hello")
async def hello() -> dict[str, str]:
    """Sanity-check endpoint the frontend pings on first load."""
    return {"message": "Hello from FastAPI — backend is reachable."}


@app.post("/admin/reload-ontologies")
@app.post("/api/admin/reload-ontologies")
async def reload_ontologies() -> dict[str, object]:
    """Load ontology YAMLs from config/ontologies and upsert them to DB.

    Returns the list of YAML files processed. If Supabase credentials are not
    configured, performs a dry-run and returns only the filenames.
    """
    loaded = load_all()
    mode = "dry-run"
    try:
        client = get_supabase()
        # Upsert each YAML into the config tables
        dirpath = get_ontology_dir()
        for name in loaded:
            if not dirpath:
                break
            path = dirpath / name
            ontology = load_yaml(path)
            upsert_to_db(client, ontology)
        mode = "applied"
    except Exception:  # no creds or client error → dry run only
        # We remain quiet for missing creds to keep endpoint usable in dev
        mode = "dry-run"
    return {"loaded": loaded, "mode": mode}


@app.get("/api/entities/{entity_id}")
async def get_entity_with_facts(entity_id: str, as_of: Optional[str] = None) -> dict[str, object]:
    """Return entity and live/disputed facts, optionally as-of a timestamp.

    If Supabase creds are missing, returns a dry-run stub with the requested params.
    """
    try:
        client = get_supabase()
    except Exception:
        return {"entity_id": entity_id, "as_of": as_of or "now", "mode": "dry-run"}

    # Load entity
    res_ent = client.table("entities").select("*").eq("id", entity_id).single().execute()
    ent = getattr(res_ent, "data", None)
    if not ent:
        raise HTTPException(status_code=404, detail="entity not found")

    as_of_ts = as_of or datetime.now(timezone.utc).isoformat()
    facts = client.rpc("facts_for_entity_as_of", {"eid": entity_id, "as_of": as_of_ts}).execute().data
    inbound = (
        client.table("facts")
        .select("*")
        .eq("object_type", "entity")
        .contains("object", [entity_id])
        .execute()
        .data
    )
    return {"entity": ent, "facts": facts or [], "inbound_facts": inbound or [], "as_of": as_of_ts}


@app.post("/api/admin/reingest")
async def reingest(body: dict = Body(...)) -> dict[str, object]:
    """Admin re-ingest: run a connector (or all) with an optional path.

    Body: { connector: string, path?: string, batch_size?: int }
    Requires Supabase creds.
    """
    try:
        client = get_supabase()
    except Exception:
        raise HTTPException(status_code=503, detail="Supabase not configured")

    connector = body.get("connector")
    if not connector:
        raise HTTPException(status_code=400, detail="connector is required")
    path = body.get("path") or "data/enterprise-bench"
    batch_size = int(body.get("batch_size") or 500)

    import pathlib

    p = pathlib.Path(path)
    written_total = 0
    if connector == "all":
        for name in ["email", "crm", "hr_record", "invoice_pdf"]:
            cls = CONNECTOR_REGISTRY.get(name) or get_connector(name)
            inst = cls()
            written = inst.ingest(p, client, batch_size=batch_size)
            written_total += written
        return {"ok": True, "written": written_total}

    cls = CONNECTOR_REGISTRY.get(connector) or get_connector(connector)
    inst = cls()
    written = inst.ingest(p, client, batch_size=batch_size)
    return {"ok": True, "written": written}
