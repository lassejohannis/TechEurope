"""Tests for Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.ingestion_models import (
    SourceRecord,
    Entity,
    Fact,
    FactStatus,
    EntityStatus,
    ExtractionStatus,
    ObjectType,
    ExtractionMethod,
)


def test_source_record_minimal():
    rec = SourceRecord(
        id="email:abc123",
        source_type="email",
        payload={"subject": "hello"},
        content_hash="a" * 64,
    )
    assert rec.extraction_status == ExtractionStatus.pending
    assert rec.superseded_by is None


def test_source_record_model_dump_no_extra_keys():
    rec = SourceRecord(
        id="email:abc",
        source_type="email",
        payload={},
        content_hash="b" * 64,
    )
    d = rec.model_dump()
    assert set(d.keys()) == {
        "id", "source_type", "source_uri", "source_native_id",
        "payload", "content_hash", "ingested_at", "superseded_by",
        "extraction_status",
    }


def test_fact_requires_non_empty_derived_from():
    with pytest.raises(ValidationError):
        Fact(
            id="f1",
            subject_id="e1",
            predicate="has_role",
            object="Engineer",
            object_type=ObjectType.string,
            confidence=0.9,
            derived_from=[],  # must be non-empty
        )


def test_fact_valid():
    f = Fact(
        id="f1",
        subject_id="e1",
        predicate="has_role",
        object="Engineer",
        object_type=ObjectType.string,
        confidence=0.95,
        derived_from=["src:abc"],
    )
    assert f.status == FactStatus.live
    assert f.confidence == 0.95


def test_fact_confidence_bounds():
    with pytest.raises(ValidationError):
        Fact(
            id="f2",
            subject_id="e1",
            predicate="p",
            object="x",
            object_type=ObjectType.string,
            confidence=1.5,  # out of bounds
            derived_from=["src:abc"],
        )


def test_entity_defaults():
    e = Entity(
        id="ent1",
        type="person",
        canonical_name="Ada Lovelace",
    )
    assert e.status == EntityStatus.live
    assert e.aliases == []
    assert e.attributes == {}


def test_strenuums_all_values():
    assert FactStatus.needs_refresh == "needs_refresh"
    assert ExtractionMethod.gemini == "gemini"
    assert ObjectType.json == "json"
