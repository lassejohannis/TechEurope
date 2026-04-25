"""FastAPI app — single process exposing the Query API for both layers."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from server.config import settings

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
