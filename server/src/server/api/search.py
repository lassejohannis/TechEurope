"""POST /search — 3-Stage Hybrid Search: Semantic ∩ Structural → Rerank.

Stage 1 — Semantic: pgvector kNN on inference_embedding (fallback: name_embedding)
Stage 2 — Structural: extract entity mentions → 1-hop graph traverse
Stage 3 — Combine (intersect if both have hits, union otherwise) + rerank
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from server.db import get_db, embed_text
from server.models import (
    EntityResponse, FactResponse,
    SearchRequest, SearchResponse, SearchResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["search"])


def _is_single_row_not_found(exc: Exception) -> bool:
    text = str(exc)
    return "PGRST116" in text or "multiple (or no) rows returned" in text


# ---------------------------------------------------------------------------
# Entity mention extraction (Pioneer stub → naive regex fallback)
# ---------------------------------------------------------------------------

def _extract_mentions(query: str) -> list[str]:
    """Return candidate entity name mentions from a query string.

    Pioneer fine-tune is wired here when WS-3 ships (replace this stub).
    Fallback: capitalised word sequences (≥2 chars, ≥1 word).
    """
    try:
        from server.extractors.pioneer import extract_mentions  # type: ignore
        return extract_mentions(query)
    except (ImportError, Exception):
        pass

    # Simple fallback: grab capitalised tokens or quoted strings
    quoted = re.findall(r'"([^"]+)"', query)
    capitalised = re.findall(r'\b([A-Z][a-zA-Z]{1,}(?:\s+[A-Z][a-zA-Z]{1,})*)\b', query)
    return list(dict.fromkeys(quoted + capitalised))  # dedupe, preserve order


def _build_entity_response(entity_row: dict, trust_row: dict | None, facts: list[dict]) -> EntityResponse:
    fact_responses = [
        FactResponse(
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
        )
        for f in facts
    ]
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


def _fetch_entity_with_trust(db, entity_id: str, as_of: datetime | None = None) -> EntityResponse | None:
    try:
        e_res = db.table("entities").select("*").eq("id", entity_id).single().execute()
        entity_row = e_res.data
    except Exception as exc:
        if _is_single_row_not_found(exc):
            return None
        raise
    if not entity_row:
        return None

    facts_q = db.table("facts").select("*").eq("subject_id", entity_id)
    if as_of:
        facts_q = facts_q.lte("valid_from", as_of.isoformat()).or_(
            f"valid_to.is.null,valid_to.gte.{as_of.isoformat()}"
        )
    else:
        facts_q = facts_q.is_("valid_to", "null")
    facts = facts_q.execute().data or []

    try:
        trust_res = db.table("entity_trust").select("*").eq("id", entity_id).single().execute()
        trust_row = trust_res.data
    except Exception as exc:
        if _is_single_row_not_found(exc):
            trust_row = None
        else:
            raise
    return _build_entity_response(entity_row, trust_row, facts)


# ---------------------------------------------------------------------------
# Hybrid search implementation
# ---------------------------------------------------------------------------

def run_hybrid_search(query: str, k: int = 10, as_of: datetime | None = None, entity_type: str | None = None, db=None) -> list[SearchResult]:
    if db is None:
        db = get_db()

    # --- Stage 1: Semantic ---
    semantic_scores: dict[str, float] = {}
    try:
        query_embedding = embed_text(query, dimensions=768)
        rpc_params: dict = {
            "query_embedding": query_embedding,
            "match_threshold": 0.65,
            "match_count": min(k * 2, 40),
            "use_inference_embedding": True,
        }
        sem_res = db.rpc("match_entities", rpc_params).execute()
        for row in sem_res.data or []:
            if entity_type and row.get("entity_type") != entity_type:
                continue
            semantic_scores[str(row["id"])] = float(row["similarity"])
    except Exception as exc:
        logger.warning("Semantic search failed (embedding unavailable?): %s", exc)

    # --- Stage 2: Structural ---
    structural_ids: set[str] = set()
    mentions = _extract_mentions(query)
    for mention in mentions[:5]:  # cap at 5 mentions
        name_res = db.table("entities").select("id").ilike(
            "canonical_name", f"%{mention}%"
        ).limit(3).execute()
        for row in name_res.data or []:
            root_id = str(row["id"])
            structural_ids.add(root_id)
            # 1-hop graph traverse
            hop_res = db.table("facts").select("subject_id, object_id").or_(
                f"subject_id.eq.{root_id},object_id.eq.{root_id}"
            ).is_("valid_to", "null").limit(20).execute()
            for f in hop_res.data or []:
                if f.get("subject_id"):
                    structural_ids.add(str(f["subject_id"]))
                if f.get("object_id"):
                    structural_ids.add(str(f["object_id"]))

    # --- Stage 3: Combine + rerank ---
    if semantic_scores and structural_ids:
        intersection = set(semantic_scores.keys()) & structural_ids
        combined_ids = intersection if intersection else (set(semantic_scores.keys()) | structural_ids)
        match_type = "hybrid"
    elif semantic_scores:
        combined_ids = set(semantic_scores.keys())
        match_type = "semantic"
    else:
        combined_ids = structural_ids
        match_type = "structural"

    results: list[SearchResult] = []
    for entity_id in list(combined_ids)[:k * 2]:
        entity = _fetch_entity_with_trust(db, entity_id, as_of)
        if not entity:
            continue
        if entity_type and entity.entity_type != entity_type:
            continue
        score = semantic_scores.get(entity_id, 0.5)
        # Boost by trust score
        final_score = score * 0.7 + entity.trust_score * 0.3
        results.append(SearchResult(entity=entity, score=final_score, match_type=match_type))

    results.sort(key=lambda r: r.score, reverse=True)
    return results[:k]


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

@router.post("/search", response_model=SearchResponse)
def search(req: SearchRequest, db=Depends(get_db)):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")

    results = run_hybrid_search(
        query=req.query,
        k=req.k,
        as_of=req.as_of,
        entity_type=req.entity_type,
        db=db,
    )
    return SearchResponse(query=req.query, results=results, total=len(results))
