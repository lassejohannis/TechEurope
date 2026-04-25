"""5-Tier Entity Resolution Cascade.

Tier 1  — Hard-ID match (emp_id, email, tax_id, product_id …)  confidence=1.0
Tier 2  — Alias table lookup (normalized name in aliases[])     confidence=0.95
Tier 3  — pgvector HNSW kNN on name_embedding / inference_embedding
Tier 3.5— Pioneer fine-tuned model hook (stub until WS-3 ships)
Tier 4  — Context heuristics (email domain → employer company)
Tier 5  — Ambiguity inbox write for 0.82–0.92 candidates

Thresholds (tune in this module):
  THRESHOLD_AUTO_MERGE = 0.92   → direct merge
  THRESHOLD_INBOX_LOW  = 0.82   → route to human review inbox
  below 0.82                    → treat as new entity
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from server.resolver.normalize import normalize_name
from server.resolver.embed import get_name_embedding

logger = logging.getLogger(__name__)

THRESHOLD_AUTO_MERGE = 0.92
THRESHOLD_INBOX_LOW = 0.82


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------

@dataclass
class CandidateEntity:
    entity_type: str  # "person" | "company" | "product" | "document" | "communication"
    canonical_name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    source_id: str = ""


@dataclass
class ResolutionResult:
    matched_id: str | None
    confidence: float
    tier: str  # "hard_id" | "alias" | "embedding" | "pioneer" | "context" | "inbox" | "new"
    signals: dict[str, Any] = field(default_factory=dict)
    action: str = "new"  # "merge" | "inbox" | "new"


# ---------------------------------------------------------------------------
# Type module registry
# ---------------------------------------------------------------------------

def _get_type_module(entity_type: str):
    from server.resolver.types import person, company, product
    return {"person": person, "company": company, "product": product}.get(entity_type)


# ---------------------------------------------------------------------------
# Tier implementations
# ---------------------------------------------------------------------------

def _tier1_hard_id(candidate: CandidateEntity, db: Any) -> ResolutionResult | None:
    type_mod = _get_type_module(candidate.entity_type)
    if type_mod is None:
        return None

    hard_ids = type_mod.extract_hard_ids(candidate.attrs)
    if not hard_ids:
        return None

    for field_name, field_value in hard_ids.items():
        try:
            # Check aliases array first (fast path for known alternate IDs)
            res = (
                db.table("entities")
                .select("id")
                .eq("entity_type", candidate.entity_type)
                .contains("aliases", [field_value])
                .limit(1)
                .execute()
            )
            if res.data:
                return ResolutionResult(
                    matched_id=str(res.data[0]["id"]),
                    confidence=1.0,
                    tier="hard_id",
                    signals={"field": field_name, "value": field_value, "via": "aliases"},
                    action="merge",
                )
            # Fallback: check attrs JSONB column
            res2 = (
                db.table("entities")
                .select("id")
                .eq("entity_type", candidate.entity_type)
                .filter(f"attrs->>{field_name}", "eq", field_value)
                .limit(1)
                .execute()
            )
            if res2.data:
                return ResolutionResult(
                    matched_id=str(res2.data[0]["id"]),
                    confidence=1.0,
                    tier="hard_id",
                    signals={"field": field_name, "value": field_value, "via": "attrs"},
                    action="merge",
                )
        except Exception as e:
            logger.debug("Tier 1 error for %s=%s: %s", field_name, field_value, e)

    return None


def _tier2_alias(candidate: CandidateEntity, db: Any) -> ResolutionResult | None:
    normalized = normalize_name(candidate.canonical_name)
    if not normalized:
        return None

    try:
        res = (
            db.table("entities")
            .select("id")
            .eq("entity_type", candidate.entity_type)
            .contains("aliases", [normalized])
            .limit(1)
            .execute()
        )
        if res.data:
            return ResolutionResult(
                matched_id=str(res.data[0]["id"]),
                confidence=0.95,
                tier="alias",
                signals={"normalized_name": normalized},
                action="merge",
            )
    except Exception as e:
        logger.debug("Tier 2 error: %s", e)

    return None


def _tier3_embedding(candidate: CandidateEntity, db: Any) -> ResolutionResult | None:
    type_mod = _get_type_module(candidate.entity_type)
    search_text = (
        type_mod.build_search_text(candidate.canonical_name, candidate.attrs)
        if type_mod
        else candidate.canonical_name
    )

    embedding = get_name_embedding(search_text)
    if embedding is None:
        return None

    try:
        res = db.rpc(
            "match_entities",
            {
                "query_embedding": embedding,
                "match_threshold": THRESHOLD_INBOX_LOW,
                "match_count": 5,
                "use_inference_embedding": True,
            },
        ).execute()

        # Filter to same entity type
        matches = [r for r in (res.data or []) if r.get("entity_type") == candidate.entity_type]
        if not matches:
            return None

        best = matches[0]
        score = float(best["similarity"])

        if score > THRESHOLD_AUTO_MERGE:
            return ResolutionResult(
                matched_id=str(best["id"]),
                confidence=score,
                tier="embedding",
                signals={"similarity": score, "matched_name": best["canonical_name"]},
                action="merge",
            )
        elif score >= THRESHOLD_INBOX_LOW:
            # Ambiguous — caller will route to Tier 5 inbox
            return ResolutionResult(
                matched_id=str(best["id"]),
                confidence=score,
                tier="embedding",
                signals={"similarity": score, "matched_name": best["canonical_name"]},
                action="inbox",
            )
    except Exception as e:
        logger.debug("Tier 3 error: %s", e)

    return None


def _tier35_pioneer(candidate: CandidateEntity) -> ResolutionResult | None:
    """Pioneer fine-tuned model hook. Returns None until WS-3 ships."""
    try:
        from server.extractors.pioneer import extract_and_match
        return extract_and_match(candidate)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Pioneer hook error (falling back to Gemini): %s", e)
    return None


def _tier4_context(candidate: CandidateEntity, db: Any) -> ResolutionResult | None:
    type_mod = _get_type_module(candidate.entity_type)
    if type_mod is None:
        return None

    signals = type_mod.extract_context_signals(candidate.attrs)

    if domain := signals.get("email_domain"):
        try:
            res = (
                db.table("entities")
                .select("id, canonical_name")
                .eq("entity_type", "company")
                .filter("attrs->>domain", "eq", domain)
                .limit(1)
                .execute()
            )
            if res.data:
                return ResolutionResult(
                    matched_id=str(res.data[0]["id"]),
                    confidence=0.85,
                    tier="context",
                    signals={"heuristic": "email_domain", "domain": domain},
                    action="merge",
                )
        except Exception as e:
            logger.debug("Tier 4 context error: %s", e)

    return None


def _write_inbox(candidate: CandidateEntity, embedding_result: ResolutionResult, db: Any) -> None:
    try:
        db.table("resolutions").insert({
            "id": str(uuid.uuid4()),
            "entity_id_1": embedding_result.matched_id,
            "entity_id_2": str(uuid.uuid4()),  # placeholder for the not-yet-created entity
            "status": "pending",
            "resolution_signals": {
                "score": embedding_result.confidence,
                "tier": "embedding",
                "candidate_name": candidate.canonical_name,
                "candidate_type": candidate.entity_type,
                "matched_name": embedding_result.signals.get("matched_name"),
                "source_id": candidate.source_id,
            },
        }).execute()
    except Exception as e:
        logger.warning("Tier 5 inbox write failed: %s", e)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve(candidate: CandidateEntity, db: Any = None) -> ResolutionResult:
    """Run the 5-tier cascade and return a ResolutionResult.

    action="merge"  → matched_id is an existing entity, caller should merge
    action="inbox"  → ambiguous match written to resolutions table for human review
    action="new"    → no match found, caller should create a new entity

    When db is None, DB-dependent tiers (1, 2, 3, 4, 5) are skipped — useful
    for unit tests that only exercise normalization and threshold logic.
    """
    # Tier 1: Hard-ID match
    if db is not None:
        result = _tier1_hard_id(candidate, db)
        if result:
            logger.info("T1 hard-id  %s → %s (%.2f)", candidate.canonical_name, result.matched_id, result.confidence)
            return result

    # Tier 2: Alias lookup
    if db is not None:
        result = _tier2_alias(candidate, db)
        if result:
            logger.info("T2 alias    %s → %s (%.2f)", candidate.canonical_name, result.matched_id, result.confidence)
            return result

    # Tier 3: Embedding kNN — hold ambiguous candidates for Tier 5
    embedding_candidate: ResolutionResult | None = None
    if db is not None:
        result = _tier3_embedding(candidate, db)
        if result:
            if result.action == "merge":
                logger.info("T3 embed    %s → %s (%.2f)", candidate.canonical_name, result.matched_id, result.confidence)
                return result
            elif result.action == "inbox":
                embedding_candidate = result  # defer to Tier 5

    # Tier 3.5: Pioneer hook
    result = _tier35_pioneer(candidate)
    if result and result.matched_id:
        logger.info("T3.5 pioneer %s → %s (%.2f)", candidate.canonical_name, result.matched_id, result.confidence)
        return result

    # Tier 4: Context heuristics
    if db is not None:
        result = _tier4_context(candidate, db)
        if result:
            logger.info("T4 context  %s → %s (%.2f)", candidate.canonical_name, result.matched_id, result.confidence)
            return result

    # Tier 5: Ambiguity inbox for deferred embedding candidates
    if embedding_candidate is not None:
        if db is not None:
            _write_inbox(candidate, embedding_candidate, db)
        logger.info("T5 inbox    %s → %s (%.2f)", candidate.canonical_name, embedding_candidate.matched_id, embedding_candidate.confidence)
        return ResolutionResult(
            matched_id=embedding_candidate.matched_id,
            confidence=embedding_candidate.confidence,
            tier="inbox",
            signals=embedding_candidate.signals,
            action="inbox",
        )

    # No match across all tiers → new entity
    return ResolutionResult(
        matched_id=None,
        confidence=0.0,
        tier="new",
        signals={"reason": "no_match_across_all_tiers"},
        action="new",
    )
