"""GET /entities/{id} — Entity card with Trust-Score + active Facts."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from server.db import get_db
from server.models import EntityResponse, FactResponse, EvidenceItem

router = APIRouter(prefix="/entities", tags=["entities"])


def _build_entity(entity_row: dict, facts: list[dict], trust_row: dict | None) -> EntityResponse:
    fact_responses = []
    for f in facts:
        evidence = []
        if f.get("source_record"):
            sr = f["source_record"]
            evidence.append(EvidenceItem(
                source=sr.get("source_type", "unknown"),
                record_id=str(sr.get("id", "")),
                confidence=f.get("confidence"),
            ))
        fact_responses.append(FactResponse(
            id=str(f["id"]),
            subject_id=str(f["subject_id"]),
            predicate=f["predicate"],
            object_id=str(f["object_id"]) if f.get("object_id") else None,
            object_literal=f.get("object_literal"),
            confidence=float(f.get("confidence", 0)),
            derivation=f.get("derivation", "unknown"),
            valid_from=f["valid_from"],
            valid_to=f.get("valid_to"),
            recorded_at=f["recorded_at"],
            source_id=str(f["source_id"]),
            status=f.get("status", "active"),
            evidence=evidence,
        ))

    return EntityResponse(
        id=str(entity_row["id"]),
        entity_type=entity_row["entity_type"],
        canonical_name=entity_row["canonical_name"],
        aliases=entity_row.get("aliases") or [],
        attrs=entity_row.get("attrs") or {},
        trust_score=float(trust_row["trust_score"]) if trust_row else 0.0,
        fact_count=int(trust_row["fact_count"]) if trust_row else 0,
        source_diversity=int(trust_row["source_diversity"]) if trust_row else 0,
        facts=fact_responses,
    )


@router.get("/{entity_id}", response_model=EntityResponse)
def get_entity(
    entity_id: str,
    as_of: datetime | None = Query(default=None, description="Time-travel: state at this timestamp"),
    db=Depends(get_db),
):
    entity_res = db.table("entities").select("*").eq("id", entity_id).single().execute()
    if not entity_res.data:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity_row = entity_res.data

    facts_q = db.table("facts").select("*, source_records(*)").eq("subject_id", entity_id)
    if as_of:
        facts_q = facts_q.lte("valid_from", as_of.isoformat()).or_(
            f"valid_to.is.null,valid_to.gte.{as_of.isoformat()}"
        )
    else:
        facts_q = facts_q.is_("valid_to", "null")
    facts_res = facts_q.execute()
    facts = facts_res.data or []

    # Flatten joined source_records into each fact dict
    for f in facts:
        sr = f.pop("source_records", None)
        f["source_record"] = sr[0] if isinstance(sr, list) and sr else sr

    trust_res = db.table("entity_trust").select("*").eq("id", entity_id).single().execute()
    trust_row = trust_res.data

    return _build_entity(entity_row, facts, trust_row)
