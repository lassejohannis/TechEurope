"""Shared Pydantic models — API responses, MCP outputs, and domain entities.

Two coexisting concerns:

1. **API/MCP response models** (``EntityResponse``, ``FactResponse``, etc.) —
   what WS-4's REST endpoints + MCP tools return.
2. **Domain models** (``SourceRecord``, ``Entity``, ``Fact``, ``Resolution``) —
   the canonical schema from ``docs/data-model.md`` used by connectors,
   resolver, and ingestion. ``ResolutionDecisionKind`` is the StrEnum form;
   ``ResolutionDecision`` (further down) is the API request payload.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Source attribution (API)
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
# Facts (API responses)
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
    trust_weight: float = 0.5


# ---------------------------------------------------------------------------
# Entities (API responses)
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
# Resolution / Ambiguity inbox (API)
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
    """API request body for resolving a pending pair."""

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


# ---------------------------------------------------------------------------
# Domain model — canonical schema (data-model.md)
# Used by connectors, resolver, ingestion.
# ---------------------------------------------------------------------------


class ExtractionStatus(StrEnum):
    pending = "pending"
    extracted = "extracted"
    failed = "failed"


class EntityStatus(StrEnum):
    live = "live"
    draft = "draft"
    archived = "archived"


class FactStatus(StrEnum):
    live = "live"
    draft = "draft"
    superseded = "superseded"
    disputed = "disputed"
    needs_refresh = "needs_refresh"


class ObjectType(StrEnum):
    entity = "entity"
    string = "string"
    number = "number"
    date = "date"
    bool = "bool"
    enum = "enum"
    json = "json"


class ExtractionMethod(StrEnum):
    rule = "rule"
    gemini = "gemini"
    pioneer = "pioneer"
    human = "human"


class ResolutionDecisionKind(StrEnum):
    """Outcome of an ambiguity-inbox resolution (domain-side)."""

    pick_one = "pick_one"
    merge = "merge"
    both_with_qualifier = "both_with_qualifier"
    reject_all = "reject_all"


class SourceRecord(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., description="hash(source_type + source_native_id)")
    source_type: str
    source_uri: str | None = None
    source_native_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    content_hash: str
    ingested_at: str | None = None
    superseded_by: str | None = None
    extraction_status: ExtractionStatus = ExtractionStatus.pending


class Entity(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = EntityStatus.live
    provenance: list[str] = Field(default_factory=list)
    inference_text: str | None = None
    embedding: list[float] | None = None
    inference_updated_at: str | None = None


class Fact(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subject_id: str
    predicate: str
    object: Any
    object_type: ObjectType
    confidence: float = Field(ge=0.0, le=1.0)
    status: FactStatus = FactStatus.live
    derived_from: list[str]
    last_hash_seen: dict[str, Any] = Field(default_factory=dict)
    valid_from: str | None = None
    valid_to: str | None = None
    ingested_at: str | None = None
    superseded_at: str | None = None
    extraction_method: ExtractionMethod | None = None
    qualifiers: dict[str, Any] = Field(default_factory=dict)
    embedding: list[float] | None = None
    superseded_by: str | None = None

    @field_validator("derived_from")
    @classmethod
    def _non_empty_derived_from(cls, v: list[str]) -> list[str]:
        if not v or len(v) == 0:
            raise ValueError("derived_from must have length >= 1")
        return v


class Resolution(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conflict_facts: list[str]
    decision: ResolutionDecisionKind
    chosen_fact_id: str | None = None
    qualifier_added: dict[str, Any] | None = None
    rationale: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None


__all__ = [
    # API / MCP
    "SourceReference",
    "EvidenceItem",
    "FactResponse",
    "ProvenanceResponse",
    "EntityResponse",
    "VfsNode",
    "VfsListResponse",
    "SearchRequest",
    "SearchResult",
    "SearchResponse",
    "ProposeFactRequest",
    "ProposeFactResponse",
    "ResolutionResponse",
    "ResolutionDecision",
    "ChangeEvent",
    # Domain
    "SourceRecord",
    "Entity",
    "Fact",
    "Resolution",
    "FactStatus",
    "EntityStatus",
    "ExtractionStatus",
    "ObjectType",
    "ExtractionMethod",
    "ResolutionDecisionKind",
]
