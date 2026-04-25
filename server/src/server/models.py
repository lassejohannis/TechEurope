"""Shared Pydantic models for API responses and MCP tool outputs."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Source attribution
# ---------------------------------------------------------------------------

class SourceReference(BaseModel):
    system: str
    path: str | None = None
    record_id: str | None = None
    timestamp: datetime | None = None
    method: str = "unknown"  # "regex_extract", "llm_gemini_2.0", "human_input", …


class EvidenceItem(BaseModel):
    source: str
    record_id: str | None = None
    quote: str | None = None
    field: str | None = None
    confidence: float | None = None


# ---------------------------------------------------------------------------
# Facts
# ---------------------------------------------------------------------------

class FactResponse(BaseModel):
    id: str
    subject_id: str
    predicate: str
    object_id: str | None = None
    object_literal: Any | None = None
    confidence: float
    derivation: str
    valid_from: datetime
    valid_to: datetime | None = None
    recorded_at: datetime
    source_id: str
    status: str = "active"
    evidence: list[EvidenceItem] = []


class ProvenanceResponse(BaseModel):
    fact: FactResponse
    source_reference: SourceReference
    superseded_by: FactResponse | None = None


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------

class EntityResponse(BaseModel):
    id: str
    entity_type: str
    canonical_name: str
    aliases: list[str] = []
    attrs: dict[str, Any] = {}
    trust_score: float = 0.0
    fact_count: int = 0
    source_diversity: int = 0
    facts: list[FactResponse] = []


# ---------------------------------------------------------------------------
# VFS
# ---------------------------------------------------------------------------

class VfsNode(BaseModel):
    path: str
    type: str
    entity_id: str
    content: dict[str, Any]
    metadata: dict[str, Any] = {}
    source_reference: SourceReference | None = None
    children: list[str] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class VfsListResponse(BaseModel):
    path: str
    children: list[VfsNode]
    total: int


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

class SearchRequest(BaseModel):
    query: str
    k: int = Field(default=10, ge=1, le=50)
    as_of: datetime | None = None
    entity_type: str | None = None


class SearchResult(BaseModel):
    entity: EntityResponse
    score: float
    match_type: str  # "semantic" | "structural" | "hybrid"
    evidence: list[EvidenceItem] = []


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


# ---------------------------------------------------------------------------
# Propose fact (VFS write)
# ---------------------------------------------------------------------------

class ProposeFactRequest(BaseModel):
    subject_id: str
    predicate: str
    object_id: str | None = None
    object_literal: Any | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_system: str = "human_input"
    source_method: str = "human_input"
    note: str | None = None


class ProposeFactResponse(BaseModel):
    fact_id: str
    source_record_id: str
    status: str = "created"


# ---------------------------------------------------------------------------
# Resolution / Ambiguity inbox
# ---------------------------------------------------------------------------

class ResolutionResponse(BaseModel):
    id: str
    entity_id_1: str
    entity_id_2: str
    status: str  # "pending" | "merged" | "rejected"
    resolution_signals: dict[str, Any] = {}
    decided_at: datetime | None = None
    decided_by: str | None = None


class ResolutionDecision(BaseModel):
    decision: str  # "merge" | "reject" | "pick_1" | "pick_2"
    decided_by: str = "human"
    note: str | None = None


# ---------------------------------------------------------------------------
# Change feed
# ---------------------------------------------------------------------------

class ChangeEvent(BaseModel):
    event_id: str
    event_type: str  # "fact_created" | "fact_superseded" | "entity_created" | …
    entity_id: str | None = None
    fact_id: str | None = None
    timestamp: datetime
    payload: dict[str, Any] = {}
