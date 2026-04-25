"""FastAPI app — Core Context Engine + Query API + MCP Server."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.responses import JSONResponse

from server.api.admin import router as admin_router
from server.api.changes import router as changes_router
from server.api.cypher import router as cypher_demo_router
from server.api.cypher_proxy import router as cypher_proxy_router
from server.api.entities import router as entities_router
from server.api.facts import router as facts_router
from server.api.graph import router as graph_router
from server.api.resolutions import router as resolutions_router
from server.api.search import router as search_router
from server.api.traverse import router as traverse_router
from server.api.vfs import router as vfs_router
from server.api.webhooks import router as webhooks_router
from server.api.webhooks_outbound import router as webhooks_outbound_router
from server.auth import get_principal
from server.config import settings
from server.sync.neo4j_projection import Neo4jProjection, SyncConfig
from server.sync.webhook_dispatcher import WebhookDispatcher

logger = logging.getLogger(__name__)


def _rate_key(request: Request) -> str:
    """Per-token when authenticated, per-IP otherwise."""
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return f"tok:{auth[7:][:32]}"
    return get_remote_address(request)


limiter = Limiter(key_func=_rate_key, default_limits=[settings.rate_limit_default])


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Boot Neo4j read-only projection (WS-5) and webhook dispatcher (#14)."""
    projection: Neo4jProjection | None = None
    listen_task: asyncio.Task[None] | None = None
    dispatcher: WebhookDispatcher | None = None
    app.state.projection = None
    app.state.dispatcher = None

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

    if settings.postgres_url:
        try:
            dispatcher = WebhookDispatcher(settings.postgres_url)
            await dispatcher.start()
            app.state.dispatcher = dispatcher
            logger.info("Webhook dispatcher active")
        except Exception as exc:
            logger.exception("Webhook dispatcher failed to start: %s", exc)
            dispatcher = None
    else:
        logger.info("Webhook dispatcher disabled (POSTGRES_URL missing)")

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
        if dispatcher:
            await dispatcher.stop()

app = FastAPI(
    title="Tech Europe — Context Engine",
    version="0.3.0",
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

# Rate limiting (slowapi) — exposes app.state.limiter for @limiter.limit decorators.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# ---------------------------------------------------------------------------
# API Routers — every /api/* router is gated by JWT/agent-token auth.
# ---------------------------------------------------------------------------

_auth_dep = [Depends(get_principal)]

app.include_router(entities_router, prefix="/api", dependencies=_auth_dep)
app.include_router(facts_router, prefix="/api", dependencies=_auth_dep)
app.include_router(search_router, prefix="/api", dependencies=_auth_dep)
app.include_router(traverse_router, prefix="/api", dependencies=_auth_dep)
app.include_router(vfs_router, prefix="/api", dependencies=_auth_dep)
app.include_router(graph_router, prefix="/api", dependencies=_auth_dep)
app.include_router(cypher_proxy_router, prefix="/api", dependencies=_auth_dep)
app.include_router(admin_router, prefix="/api", dependencies=_auth_dep)
app.include_router(webhooks_router, prefix="/api", dependencies=_auth_dep)  # inbound source-change
app.include_router(webhooks_outbound_router, prefix="/api", dependencies=_auth_dep)  # outbound /admin/webhooks
app.include_router(changes_router, dependencies=_auth_dep)  # already has /api/changes prefix
app.include_router(resolutions_router, dependencies=_auth_dep)  # /api/resolutions + /api/fact-resolutions + /api/trust-weights

# WS-5: live Aura demo endpoints under /query/cypher (no auth — demo-only)
app.include_router(cypher_demo_router)

# ---------------------------------------------------------------------------
# MCP Server (mounted at /mcp — SSE transport for MCP clients)
# ---------------------------------------------------------------------------

try:
    from server.mcp.server import build_sse_app

    app.mount("/mcp", build_sse_app())
    logger.info("MCP server mounted at /mcp")
except Exception as exc:
    logger.warning("MCP server could not be mounted: %s", exc)


# ---------------------------------------------------------------------------
# Health + legacy hello (no auth — used by uptime probes and the Vite proxy)
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    mcp_endpoint: str
    openapi_endpoint: str
    auth_enabled: bool


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="tech-europe-server",
        version="0.3.0",
        mcp_endpoint="/mcp/sse",
        openapi_endpoint="/docs",
        auth_enabled=not settings.api_auth_disabled,
    )


@app.get("/api/hello")
def hello() -> dict[str, str]:
    return {"message": "Hello from FastAPI — backend is reachable."}
