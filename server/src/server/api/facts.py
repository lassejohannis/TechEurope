"""Facts router: provenance + validate / flag / edit (write paths).

Edit follows the bi-temporal supersede pattern from vfs.propose_fact: never
mutate an existing live fact in place — instead insert a new fact, and let
the Postgres supersede-trigger close the prior one.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from server.auth import Principal, require_scope
from server.db import get_db
from server.models import FactResponse, ProvenanceResponse, SourceReference, EvidenceItem

router = APIRouter(prefix="/facts", tags=["facts"])


def _is_single_row_not_found(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST116" in text or "multiple (or no) rows returned" in text


class FactValidateRequest(BaseModel):
    note: str | None = None


class FactFlagRequest(BaseModel):
    reason: str = Field(..., min_length=3)


class FactEditRequest(BaseModel):
    object_id: str | None = None
    object_literal: Any | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    note: str | None = None


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
    try:
        fact_res = db.table("facts").select("*, source_records(*)").eq("id", fact_id).single().execute()
        f = fact_res.data
    except Exception as exc:
        if _is_single_row_not_found(exc):
            raise HTTPException(status_code=404, detail="Fact not found") from exc
        raise
    if not f:
        raise HTTPException(status_code=404, detail="Fact not found")

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
        try:
            sup_res = db.table("facts").select("*").eq("id", f["superseded_by"]).single().execute()
            s = sup_res.data
            if s:
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
        except Exception as exc:
            if not _is_single_row_not_found(exc):
                raise

    return ProvenanceResponse(
        fact=fact_resp,
        source_reference=source_ref,
        superseded_by=superseded_by,
    )


def _load_fact_or_404(db, fact_id: str) -> dict[str, Any]:
    res = db.table("facts").select("*").eq("id", fact_id).single().execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="Fact not found")
    return res.data


@router.post("/{fact_id}/validate", status_code=200)
def validate_fact(
    fact_id: str,
    req: FactValidateRequest | None = None,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
):
    """Mark a fact as human-validated. Writes a fact_changes audit row but does
    NOT supersede — validation is a confidence boost, not a new version."""
    fact = _load_fact_or_404(db, fact_id)
    now = datetime.now(tz=timezone.utc).isoformat()
    db.table("fact_changes").insert({
        "kind": "validate",
        "fact_id": fact_id,
        "old_value": None,
        "new_value": {"validated": True, "note": (req.note if req else None)},
        "triggered_by": principal.subject,
        "at": now,
    }).execute()
    return {"fact_id": fact_id, "validated_by": principal.subject, "at": now, "previous_status": fact.get("status")}


@router.post("/{fact_id}/flag", status_code=200)
def flag_fact(
    fact_id: str,
    req: FactFlagRequest,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
):
    """Mark a fact as suspect. Sets status='disputed' and writes audit row."""
    fact = _load_fact_or_404(db, fact_id)
    now = datetime.now(tz=timezone.utc).isoformat()
    db.table("facts").update({"status": "disputed"}).eq("id", fact_id).execute()
    db.table("fact_changes").insert({
        "kind": "flag",
        "fact_id": fact_id,
        "old_value": {"status": fact.get("status")},
        "new_value": {"status": "disputed", "reason": req.reason},
        "triggered_by": principal.subject,
        "at": now,
    }).execute()
    return {"fact_id": fact_id, "status": "disputed", "flagged_by": principal.subject}


@router.post("/{fact_id}/edit", response_model=FactResponse, status_code=201)
def edit_fact(
    fact_id: str,
    req: FactEditRequest,
    db=Depends(get_db),
    principal: Principal = Depends(require_scope("write")),
):
    """Write a NEW fact superseding the original. Bi-temporal: original gets
    superseded_at via Postgres trigger; new one is the live row."""
    if req.object_id is None and req.object_literal is None:
        raise HTTPException(status_code=400, detail="Provide object_id or object_literal")

    original = _load_fact_or_404(db, fact_id)
    now = datetime.now(tz=timezone.utc).isoformat()

    # 1. SourceRecord for audit
    sr_id = str(uuid.uuid4())
    db.table("source_records").insert({
        "id": sr_id,
        "source_type": "human_edit",
        "source_id": f"human_edit:{sr_id}",
        "event_type": "fact_edit",
        "raw_content": req.note or f"Edit of fact {fact_id}",
        "timestamp": now,
        "metadata": {"method": "human_input", "edited_by": principal.subject, "supersedes": fact_id},
    }).execute()

    # 2. Insert new fact (Postgres exclude-constraint + trigger handle the supersede)
    new_id = str(uuid.uuid4())
    db.table("facts").insert({
        "id": new_id,
        "subject_id": original["subject_id"],
        "predicate": original["predicate"],
        "object_id": req.object_id,
        "object_literal": req.object_literal,
        "confidence": req.confidence,
        "source_id": sr_id,
        "derivation": "human_edit",
        "valid_from": now,
        "status": "active",
    }).execute()

    # 3. Mark original as superseded_by the new fact
    db.table("facts").update({
        "superseded_by": new_id,
        "valid_to": now,
        "status": "superseded",
    }).eq("id", fact_id).execute()

    new_row = db.table("facts").select("*").eq("id", new_id).single().execute().data
    return FactResponse(
        id=new_row["id"],
        subject_id=new_row["subject_id"],
        predicate=new_row["predicate"],
        object_id=new_row.get("object_id"),
        object_literal=new_row.get("object_literal"),
        confidence=float(new_row.get("confidence", 0)),
        derivation=new_row.get("derivation", "human_edit"),
        valid_from=new_row["valid_from"],
        valid_to=new_row.get("valid_to"),
        recorded_at=new_row["recorded_at"],
        source_id=str(new_row["source_id"]),
        status=new_row.get("status", "active"),
    )
