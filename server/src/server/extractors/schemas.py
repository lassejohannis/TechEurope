"""Shared schemas for SourceRecord, Entity, Fact, Resolution.

Contract spec lives in docs/data-model.md. This is the lean, in-memory shape used
by extractors and the synthetic-data pipeline (WS-3); DB-backed types come with WS-0.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "email",
    "crm_contact",
    "hr_record",
    "policy_doc",
    "ticket",
    "chat_message",
    "meeting_note",
    "github_repo",
    "github_issue",
    "invoice",
    "resume",
    "social_post",
    "sales_record",
    "qa_post",
    "human_resolution",
]

# Entity types are no longer a closed Literal — the autonomous-ontology
# work writes new types into entity_type_config at runtime. The downstream
# trigger on `entities.entity_type` enforces "must be approved", so type
# safety is preserved at the DB layer rather than the Python schema layer.
EntityType = str

ObjectType = Literal["entity", "string", "number", "date", "bool", "enum"]
FactStatus = Literal["live", "draft", "superseded", "disputed"]
EntityStatus = Literal["live", "draft", "archived"]


class SourceRecord(BaseModel):
    id: str
    source_type: SourceType
    source_uri: str
    source_native_id: str
    payload: dict[str, Any]
    content_hash: str
    ingested_at: datetime
    superseded_by: str | None = None


class Entity(BaseModel):
    id: str
    type: EntityType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    status: EntityStatus = "live"
    provenance: list[str] = Field(default_factory=list)


class Fact(BaseModel):
    subject: str
    predicate: str
    object: str | int | float | bool
    object_type: ObjectType
    confidence: float = Field(ge=0.0, le=1.0)
    status: FactStatus = "live"
    derived_from: list[str] = Field(default_factory=list)
    qualifiers: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    """What an extractor returns for one text chunk.

    Used both as Gemini's structured output target and as the JSONL
    training-pair shape we hand to Pioneer.
    """

    entities: list[Entity]
    facts: list[Fact]


class TrainingPair(BaseModel):
    """One row in pioneer_training.jsonl."""

    source_record_id: str
    chunk_id: str
    text: str
    output: ExtractionResult
