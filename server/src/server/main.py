"""FastAPI app — Core Context Engine + Query API + MCP Server."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.api.admin import router as admin_router
from server.api.changes import router as changes_router
from server.api.cypher import router as cypher_demo_router
from server.api.cypher_proxy import router as cypher_proxy_router
from server.api.entities import router as entities_router
from server.api.facts import router as facts_router
from server.api.search import router as search_router
from server.api.traverse import router as traverse_router
from server.api.vfs import router as vfs_router
from server.api.webhooks import router as webhooks_router
from server.config import settings
from server.db import get_supabase
from server.ontology.loader import get_ontology_dir, load_all, load_yaml, upsert_to_db
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
                neo4j_user=settings.neo4j_user,
                neo4j_password=settings.neo4j_password,
                neo4j_database=settings.neo4j_database,
                supabase_url=settings.supabase_url,
                supabase_secret_key=settings.supabase_secret_key,
            )
        )
        try:
            await projection.start()
            # replay_all can take 30s+ for large datasets — run in background so
            # the server starts accepting requests immediately.
            asyncio.create_task(projection.replay_all(), name="neo4j-replay")
            listen_task = asyncio.create_task(projection.listen(), name="neo4j-listen")
            app.state.projection = projection
            logger.info("WS-5 Neo4j projection active (replay running in background)")
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
    version="0.2.0",
    description=(
        "Qontext-track Context Layer: VFS, Entity Resolution, Graph, Query API, MCP Tools.\n\n"
        "Core principle: no revenue/domain semantics in this layer. "
        "Everything is entities, facts, and time."
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

# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------
# WS-4: REST query surface mounted under /api
app.include_router(entities_router, prefix="/api")
app.include_router(facts_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(traverse_router, prefix="/api")
app.include_router(vfs_router, prefix="/api")
app.include_router(cypher_proxy_router, prefix="/api")
app.include_router(webhooks_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(changes_router)  # already has /api/changes prefix

# WS-5: live Aura demo endpoints under /query/cypher (own prefix in router)
app.include_router(cypher_demo_router)

# ---------------------------------------------------------------------------
# MCP Server (mounted at /mcp — SSE transport for MCP clients)
# ---------------------------------------------------------------------------

try:
    from server.mcp.server import mcp as mcp_server

    app.mount("/mcp", mcp_server.sse_app())
    logger.info("MCP server mounted at /mcp")
except Exception as exc:
    logger.warning("MCP server could not be mounted: %s", exc)


# ---------------------------------------------------------------------------
# Health + legacy hello
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    mcp_endpoint: str
    openapi_endpoint: str


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="tech-europe-server",
        version="0.2.0",
        mcp_endpoint="/mcp/sse",
        openapi_endpoint="/docs",
    )


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI — backend is reachable."}
