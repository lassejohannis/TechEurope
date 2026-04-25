"""FastAPI app — single process exposing the Query API for both layers."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.config import settings
from server.db import get_supabase
from server.ontology.loader import load_all, upsert_to_db

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
        from pathlib import Path
        import yaml  # noqa: F401

        for name in loaded:
            path = __import__("pathlib").Path("config/ontologies") / name
            from server.ontology.loader import load_yaml

            ontology = load_yaml(path)
            upsert_to_db(client, ontology)
        mode = "applied"
    except Exception as exc:  # no creds or client error → dry run only
        # We remain quiet for missing creds to keep endpoint usable in dev
        mode = "dry-run"
    return {"loaded": loaded, "mode": mode}
