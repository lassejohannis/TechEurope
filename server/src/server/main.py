"""FastAPI app — Core Context Engine + Query API + MCP Server."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.config import settings

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tech Europe — Context Engine",
    version="0.2.0",
    description=(
        "Qontext-track Context Layer: VFS, Entity Resolution, Graph, Query API, MCP Tools.\n\n"
        "Core principle: no revenue/domain semantics in this layer. "
        "Everything is entities, facts, and time."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API Routers (WS-4)
# ---------------------------------------------------------------------------

from server.api.entities import router as entities_router
from server.api.facts import router as facts_router
from server.api.search import router as search_router
from server.api.vfs import router as vfs_router
from server.api.cypher_proxy import router as cypher_router
from server.api.admin import router as admin_router

app.include_router(entities_router, prefix="/api")
app.include_router(facts_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(vfs_router, prefix="/api")
app.include_router(cypher_router, prefix="/api")
app.include_router(admin_router, prefix="/api")

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
