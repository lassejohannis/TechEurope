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
from functools import lru_cache
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
    # Cross-type relationship hint (Tier 4 emits these instead of merging into
    # a different-typed entity). Format: (predicate, target_entity_type, target_id).
    relationship_hint: tuple[str, str, str] | None = None


# ---------------------------------------------------------------------------
# Type adapter — Python module if it exists, else config from entity_type_config
# ---------------------------------------------------------------------------

# Default fields treated as hard IDs when nothing else declares them.
# Domain-agnostic IDs that show up across many enterprise data sources.
_GENERIC_HARD_ID_HINTS = (
    "email", "emp_id", "tax_id", "domain", "product_id",
    "isbn", "doi", "account_number", "iban", "bic", "device_id",
    "external_id", "uuid",
)


def _get_type_module(entity_type: str):
    """Return a per-type Python module if it exists, else None.

    Five legacy modules ship with the codebase (`person`, `company`,
    `product`, `document`, `communication`). For any other entity_type,
    the cascade falls back on the config-driven `_config_type_adapter`.
    """
    from server.resolver.types import communication, company, document, person, product
    return {
        "person": person,
        "company": company,
        "product": product,
        "document": document,
        "communication": communication,
    }.get(entity_type)


@lru_cache(maxsize=128)
def _load_entity_type_config(entity_type: str) -> dict[str, Any]:
    """Read entity_type_config.config from DB, cached.

    Expected shape (set by `cmd_infer_source_mappings` when a new type is
    auto-approved):
        {
          "hard_id_fields": ["email", "external_id"],
          "search_attrs": ["title", "department"],
          ...
        }
    Missing keys default to empty / generic.
    """
    try:
        from server.db import get_supabase
        db = get_supabase()
        res = (
            db.table("entity_type_config")
            .select("config")
            .eq("id", entity_type)
            .limit(1)
            .execute()
        )
        if res.data:
            cfg = res.data[0].get("config") or {}
            if isinstance(cfg, dict):
                return cfg
    except Exception:
        # Cascade must never break on config-read errors.
        pass
    return {}


def _hard_id_fields_for(entity_type: str, attrs: dict[str, Any]) -> list[str]:
    """Determine which attr keys to treat as hard IDs for this entity_type.

    Resolution order:
    1. Python module's `HARD_ID_FIELDS` (legacy 5 types)
    2. `entity_type_config.config.hard_id_fields` (config-driven, set by
       `infer-source-mappings` when the AI proposes a new type)
    3. Generic fallback: any attr key in `_GENERIC_HARD_ID_HINTS` that exists
       on this candidate's attrs (lets us still extract obvious hard IDs even
       for types nobody has configured yet).
    """
    mod = _get_type_module(entity_type)
    if mod is not None and hasattr(mod, "HARD_ID_FIELDS"):
        return list(getattr(mod, "HARD_ID_FIELDS"))
    cfg = _load_entity_type_config(entity_type)
    declared = cfg.get("hard_id_fields")
    if isinstance(declared, list) and declared:
        return [str(f) for f in declared if isinstance(f, str)]
    return [k for k in _GENERIC_HARD_ID_HINTS if k in (attrs or {})]


def _extract_hard_ids(entity_type: str, attrs: dict[str, Any]) -> dict[str, str]:
    """Module-or-config-driven hard-ID extraction.

    Returns a dict[field_name → normalized_value] that the cascade's Tier 1
    can search for in entity rows.
    """
    if not attrs:
        return {}
    mod = _get_type_module(entity_type)
    if mod is not None and hasattr(mod, "extract_hard_ids"):
        return mod.extract_hard_ids(attrs)
    fields = _hard_id_fields_for(entity_type, attrs)
    return {k: str(attrs[k]).lower() for k in fields if attrs.get(k)}


def _build_search_text(entity_type: str, canonical_name: str, attrs: dict[str, Any]) -> str:
    """Module-or-config-driven Tier-A search-text builder."""
    mod = _get_type_module(entity_type)
    if mod is not None and hasattr(mod, "build_search_text"):
        return mod.build_search_text(canonical_name, attrs or {})
    cfg = _load_entity_type_config(entity_type)
    extra_keys = cfg.get("search_attrs") or []
    if not isinstance(extra_keys, list):
        extra_keys = []
    parts: list[str] = [canonical_name]
    for k in extra_keys:
        if isinstance(k, str) and (v := (attrs or {}).get(k)):
            parts.append(str(v))
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Tier implementations
# ---------------------------------------------------------------------------

def _tier1_hard_id(candidate: CandidateEntity, db: Any) -> ResolutionResult | None:
    hard_ids = _extract_hard_ids(candidate.entity_type, candidate.attrs)
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
    search_text = _build_search_text(
        candidate.entity_type, candidate.canonical_name, candidate.attrs
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
    """Cross-type relationship hint, NOT an entity match.

    A person whose email domain matches an existing company is *employed there*
    — they are not the same entity. So T4 returns ``matched_id=None`` plus a
    ``relationship_hint`` that the caller persists as a Fact (e.g. works_at).
    """
    type_mod = _get_type_module(candidate.entity_type)
    if type_mod is None:
        return None

    signals = type_mod.extract_context_signals(candidate.attrs)

    if domain := signals.get("email_domain"):
        try:
            res = (
                db.table("entities")
                .select("id, canonical_name, entity_type")
                .eq("entity_type", "company")
                .filter("attrs->>domain", "eq", domain)
                .limit(1)
                .execute()
            )
            if res.data and candidate.entity_type != "company":
                target = res.data[0]
                # works_at is the canonical person→company hint; other types
                # could carry different predicates later, keep mapping local.
                predicate = "works_at" if candidate.entity_type == "person" else "related_to"
                return ResolutionResult(
                    matched_id=None,
                    confidence=0.85,
                    tier="context",
                    signals={"heuristic": "email_domain", "domain": domain,
                             "matched_company_id": str(target["id"])},
                    action="new",  # candidate is still a new entity of its own type
                    relationship_hint=(predicate, str(target["entity_type"]), str(target["id"])),
                )
        except Exception as e:
            logger.debug("Tier 4 context error: %s", e)

    return None


def _candidate_id(candidate: CandidateEntity) -> str:
    """Deterministic ID for a candidate — must match cli._entity_id."""
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", candidate.canonical_name.lower()).strip("-") or "unnamed"
    return f"{candidate.entity_type}:{slug}"


def write_pending_inbox(candidate: CandidateEntity, embedding_result: ResolutionResult, db: Any) -> None:
    """Public entry: caller invokes after the candidate has been persisted."""
    _write_inbox(candidate, embedding_result, db)


def _write_inbox(candidate: CandidateEntity, embedding_result: ResolutionResult, db: Any) -> None:
    """Write a pending entity-pair to the ambiguity inbox.

    entity_id_2 is the deterministic ID the candidate *will* have once persisted,
    so the FK to entities resolves cleanly. The candidate must exist before the
    inbox row becomes user-visible — caller's responsibility (cli.cmd_resolve
    persists the candidate first via _persist_entity).
    """
    candidate_eid = _candidate_id(candidate)
    try:
        db.table("resolutions").insert({
            "id": str(uuid.uuid4()),
            "entity_id_1": embedding_result.matched_id,
            "entity_id_2": candidate_eid,
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

    # Tier 5: Ambiguity inbox for deferred embedding candidates.
    # We DON'T write the inbox row here because the candidate hasn't been
    # persisted yet (FK constraint on resolutions.entity_id_2 → entities.id
    # would fail). Caller invokes write_pending_inbox(...) after persisting.
    if embedding_candidate is not None:
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
