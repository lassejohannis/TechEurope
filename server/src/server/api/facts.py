"""GET /facts/{id}/provenance — Evidence chain for a single fact."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.db import get_db
from server.models import FactResponse, ProvenanceResponse, SourceReference, EvidenceItem

router = APIRouter(prefix="/facts", tags=["facts"])


def _source_ref_from_record(sr: dict) -> SourceReference:
    meta = sr.get("metadata") or {}
    return SourceReference(
        system=sr.get("source_type", "unknown"),
        path=meta.get("path") or sr.get("source_id"),
        record_id=str(sr["id"]),
        timestamp=sr.get("timestamp") or sr.get("ingested_at"),
        method=meta.get("method", "unknown"),
    )


@router.get("/{fact_id}/provenance", response_model=ProvenanceResponse)
def get_provenance(fact_id: str, db=Depends(get_db)):
    fact_res = db.table("facts").select("*, source_records(*)").eq("id", fact_id).single().execute()
    if not fact_res.data:
        raise HTTPException(status_code=404, detail="Fact not found")
    f = fact_res.data

    sr_list = f.pop("source_records", None)
    sr = sr_list[0] if isinstance(sr_list, list) and sr_list else sr_list
    if not sr:
        raise HTTPException(status_code=404, detail="Source record missing for fact")

    source_ref = _source_ref_from_record(sr)
    evidence = [EvidenceItem(
        source=sr.get("source_type", "unknown"),
        record_id=str(sr["id"]),
        quote=sr.get("raw_content", "")[:300] if sr.get("raw_content") else None,
        confidence=f.get("confidence"),
    )]

    fact_resp = FactResponse(
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
    )

    superseded_by = None
    if f.get("superseded_by"):
        sup_res = db.table("facts").select("*").eq("id", f["superseded_by"]).single().execute()
        if sup_res.data:
            s = sup_res.data
            superseded_by = FactResponse(
                id=str(s["id"]),
                subject_id=str(s["subject_id"]),
                predicate=s["predicate"],
                object_id=str(s["object_id"]) if s.get("object_id") else None,
                object_literal=s.get("object_literal"),
                confidence=float(s.get("confidence", 0)),
                derivation=s.get("derivation", "unknown"),
                valid_from=s["valid_from"],
                valid_to=s.get("valid_to"),
                recorded_at=s["recorded_at"],
                source_id=str(s["source_id"]),
            )

    return ProvenanceResponse(
        fact=fact_resp,
        source_reference=source_ref,
        superseded_by=superseded_by,
    )
