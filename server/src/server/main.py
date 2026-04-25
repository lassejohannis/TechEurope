"""FastAPI app — single process exposing the Query API for both layers."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.api.cypher import router as cypher_router
from server.config import settings
from server.sync.neo4j_projection import Neo4jProjection, SyncConfig

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot the Neo4j read-only projection (WS-5) if configured."""
    projection: Neo4jProjection | None = None
    listen_task: asyncio.Task[None] | None = None
    app.state.projection = None

    if settings.neo4j_enabled and settings.supabase_secret_key:
        projection = Neo4jProjection(
            SyncConfig(
                neo4j_uri=settings.neo4j_uri,
                neo4j_user=settings.neo4j_username,
                neo4j_password=settings.neo4j_password,
                neo4j_database=settings.neo4j_database,
                supabase_url=settings.supabase_url,
                supabase_secret_key=settings.supabase_secret_key,
            )
        )
        try:
            await projection.start()
            await projection.replay_all()
            listen_task = asyncio.create_task(projection.listen(), name="neo4j-listen")
            app.state.projection = projection
            logger.info("WS-5 Neo4j projection active")
        except Exception as exc:
            logger.exception("Neo4j projection failed to start (%s) — Postgres-only", exc)
            if projection:
                await projection.stop()
            projection = None
    else:
        logger.info("Neo4j projection disabled (NEO4J_URI / SUPABASE_SECRET_KEY missing)")

    try:
        yield
    finally:
        if listen_task:
            listen_task.cancel()
            try:
                await listen_task
            except (asyncio.CancelledError, Exception):
                pass
        if projection:
            await projection.stop()


app = FastAPI(
    title="Tech Europe — Context Engine",
    version="0.1.0",
    description=(
        "Boilerplate for the Big Berlin Hack 2026 (Qontext track). "
        "Day-1 work fills in Core Context Engine endpoints + Revenue App routes."
    ),
    lifespan=lifespan,
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


app.include_router(cypher_router)
