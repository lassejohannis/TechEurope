from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict, field_validator


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


class ResolutionDecision(StrEnum):
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
    decision: ResolutionDecision
    chosen_fact_id: str | None = None
    qualifier_added: dict[str, Any] | None = None
    rationale: str | None = None
    resolved_by: str | None = None
    resolved_at: str | None = None


__all__ = [
    "SourceRecord",
    "Entity",
    "Fact",
    "Resolution",
    "FactStatus",
    "EntityStatus",
    "ExtractionStatus",
    "ObjectType",
    "ExtractionMethod",
    "ResolutionDecision",
]

