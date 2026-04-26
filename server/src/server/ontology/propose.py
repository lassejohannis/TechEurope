"""Autonomous ontology inference: ask Gemini to design extractors for new sources.

Two entry points:

- ``infer_source_mapping(source_type, sample_records, db)`` — given 5 sample
  records of an unknown source_type, ask Gemini 2.5 Pro to design a JSONata
  mapping config. Validates the proposal against a held-out sample before
  writing it as ``status='pending'`` to ``source_type_mapping``.

- ``propose_or_match_type(name, kind, db)`` — embedding-similarity check
  against existing approved types. < 0.4 distance → reuse existing.
  > 0.4 distance → write a pending row to entity_type_config / edge_type_config.

Auto-approve threshold (`auto_approve_proposal()`) lets the hybrid workflow
skip human review when the proposal is high-confidence and clearly distinct
from anything existing.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

from server.config import settings
from server.db import embed_text

logger = logging.getLogger(__name__)

GEMINI_INFERENCE_MODELS = (
    "gemini-2.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
)
SIMILARITY_REUSE = 0.85  # cosine ≥ this ⇒ same type as existing
SIMILARITY_REJECT_NEW = 0.4  # if new proposal is < this distance from existing ⇒ reuse instead
AUTO_APPROVE_CONFIDENCE = 0.95
AUTO_APPROVE_VALIDATION_RATE = 0.6  # ≥ N% of sample records produce ≥1 entity


# ---------------------------------------------------------------------------
# Pydantic schemas for AI output
# ---------------------------------------------------------------------------


class EntitySpec(BaseModel):
    type: str
    canonical_name: str = Field(description="JSONata expression resolving to a string")
    hard_ids: dict[str, str] = Field(default_factory=dict, description="field name → JSONata expression")
    extra_attrs: dict[str, str] = Field(default_factory=dict)


class FactSpec(BaseModel):
    subject_canonical_name: str
    subject_type: str
    predicate: str
    object_canonical_name: str | None = None
    object_type: str | None = None
    object_literal: str | None = Field(default=None, description="JSONata for scalar/json target")
    confidence: float | None = None
    extraction_method: Literal["rule"] = "rule"


class MappingProposal(BaseModel):
    """The AI's proposed mapping for a new source_type."""

    source_type: str
    rationale: str
    entities: list[EntitySpec] = Field(default_factory=list)
    facts: list[FactSpec] = Field(default_factory=list)
    free_text_paths: list[str] = Field(default_factory=list)
    free_text_sender: str | None = None
    free_text_recipient: str | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    new_entity_types: list[str] = Field(
        default_factory=list,
        description="entity_type ids referenced above that don't exist yet — proposed for creation",
    )
    new_edge_types: list[str] = Field(
        default_factory=list,
        description="predicate ids referenced above that don't exist yet — proposed for creation",
    )


# ---------------------------------------------------------------------------
# Inference
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _approved_types(db: Any) -> tuple[list[str], list[str]]:
    """Return (approved_entity_type_ids, approved_edge_type_ids)."""
    e = (
        db.table("entity_type_config")
        .select("id")
        .eq("approval_status", "approved")
        .execute()
    )
    g = (
        db.table("edge_type_config")
        .select("id")
        .eq("approval_status", "approved")
        .execute()
    )
    return (
        sorted({r["id"] for r in (e.data or [])}),
        sorted({r["id"] for r in (g.data or [])}),
    )


def _build_inference_prompt(
    source_type: str,
    sample_records: list[dict[str, Any]],
    approved_entity_types: list[str],
    approved_edge_types: list[str],
) -> str:
    sample_payloads = [r.get("payload") or {} for r in sample_records[:5]]
    return f"""You are designing a JSONata-based extraction config for a new data source.

Source type: {source_type!r}

Existing approved entity types you may REUSE:
{', '.join(approved_entity_types) or '(none yet)'}

Existing approved predicates (edges) you may REUSE:
{', '.join(approved_edge_types) or '(none yet)'}

Here are 5 sample payloads from this source:
{json.dumps(sample_payloads, indent=2, default=str)[:6000]}

Your job:
1. Identify the entities each payload describes (people, organizations,
   communications, documents, …). Prefer REUSING the existing types above —
   only invent a new entity_type if nothing fits semantically.
2. Identify the relationships between those entities. Prefer REUSING existing
   predicates — only invent new ones for novel relationships.
3. Express each field via JSONata. Examples:
   - "$.author.name"
   - "$lowercase(reporter.email)"
   - "$substringAfter(reporter.email, '@')"
   - "$uppercase($substringBefore($substringAfter(sender_email, '@'), '.'))"
4. List all referenced entity_types you are NEWLY proposing in
   `new_entity_types`. Same for predicates in `new_edge_types`.
5. If there are unstructured text fields (body, description, comments) that
   may contain implicit relationship statements, list their JSONata paths in
   `free_text_paths` and identify sender/recipient JSONata for them.
6. confidence: how sure are you the mapping is correct? 0.0 to 1.0.

Output ONLY valid JSON matching the MappingProposal schema. No prose.
"""


def _gemini_safe_schema(schema: dict) -> dict:
    """Strip JSON-Schema features that the Gemini API rejects.

    Gemini doesn't support: additionalProperties, $ref-resolution to be
    embedded inline, arbitrary enum mixed with anyOf. We do a deep-copy
    and prune those keys recursively.
    """
    import copy

    schema = copy.deepcopy(schema)

    def scrub(node):
        if isinstance(node, dict):
            node.pop("additionalProperties", None)
            node.pop("title", None)
            node.pop("$defs", None)
            node.pop("default", None)
            for v in list(node.values()):
                scrub(v)
        elif isinstance(node, list):
            for v in node:
                scrub(v)

    # Inline any $ref pointers (Gemini doesn't dereference them).
    defs = schema.get("$defs") or {}

    def inline(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if ref and ref.startswith("#/$defs/"):
                key = ref.split("/")[-1]
                target = defs.get(key)
                if target:
                    node.clear()
                    node.update(copy.deepcopy(target))
                    inline(node)
                    return
            for k, v in node.items():
                inline(v)
        elif isinstance(node, list):
            for v in node:
                inline(v)

    inline(schema)
    scrub(schema)
    return schema


def infer_source_mapping(
    source_type: str,
    sample_records: list[dict[str, Any]],
    db: Any,
) -> MappingProposal | None:
    """Ask Gemini 2.5 Pro to design a JSONata mapping for this source_type."""
    if not settings.gemini_api_key or not sample_records:
        return None
    try:
        from google import genai  # type: ignore
    except Exception:
        return None

    approved_e, approved_p = _approved_types(db)

    prompt = _build_inference_prompt(source_type, sample_records, approved_e, approved_p)
    schema = _gemini_safe_schema(MappingProposal.model_json_schema())

    from server.gemini_budget import gemini_call

    client = genai.Client(api_key=settings.gemini_api_key)
    last_err = None
    for model_id in GEMINI_INFERENCE_MODELS:
        try:
            resp = gemini_call(
                model_id,
                lambda m=model_id: client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                ),
            )
            if resp is None:
                # cap or cooldown — bail out, don't burn through more models
                return None
            raw = getattr(resp, "text", None) or "{}"
            proposal = MappingProposal.model_validate_json(raw)
            logger.info("inferred mapping for %s via %s (conf=%.2f)",
                        source_type, model_id, proposal.confidence)
            return proposal
        except Exception as exc:
            last_err = exc
            logger.warning("inference via %s failed: %s", model_id, exc)
            continue
    logger.warning(
        "infer_source_mapping for %s exhausted all models: %s", source_type, last_err
    )
    return None


# ---------------------------------------------------------------------------
# Validation: run the proposal against held-out samples
# ---------------------------------------------------------------------------


def validate_proposal(
    proposal: MappingProposal,
    holdout_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return validation stats: how often the mapping produces entities/facts."""
    from server.ontology.engine import apply_mapping

    cfg = proposal.model_dump()
    counts = {"records": len(holdout_records), "entities_total": 0, "facts_total": 0,
              "records_with_entity": 0, "records_with_fact": 0}
    for rec in holdout_records:
        ents, facts = apply_mapping(rec, cfg)
        counts["entities_total"] += len(ents)
        counts["facts_total"] += len(facts)
        if ents:
            counts["records_with_entity"] += 1
        if facts:
            counts["records_with_fact"] += 1
    counts["entity_rate"] = (
        counts["records_with_entity"] / counts["records"] if counts["records"] else 0
    )
    counts["fact_rate"] = (
        counts["records_with_fact"] / counts["records"] if counts["records"] else 0
    )
    return counts


# ---------------------------------------------------------------------------
# Persistence: write proposal as a pending row
# ---------------------------------------------------------------------------


def persist_proposal(
    proposal: MappingProposal,
    db: Any,
    sample_ids: list[str],
    validation_stats: dict[str, Any],
    auto_approve: bool = False,
) -> str:
    """Write the proposal to source_type_mapping (status pending or approved)."""
    status = "approved" if auto_approve else "pending"
    row = {
        "id": proposal.source_type,
        "source_type": proposal.source_type,
        "config": proposal.model_dump(),
        "status": status,
        "validation_stats": validation_stats,
        "created_from_sample_ids": sample_ids,
        "rationale": proposal.rationale,
    }
    if auto_approve:
        row["approved_at"] = _now_iso()
        row["approved_by"] = "auto_threshold"
    db.table("source_type_mapping").upsert(row, on_conflict="source_type").execute()

    # Also ensure that any new entity/edge types referenced exist as pending rows
    for new_e in proposal.new_entity_types or []:
        if not new_e:
            continue
        emb = embed_text(new_e)
        db.table("entity_type_config").upsert(
            {
                "id": new_e,
                "config": {"description": f"Auto-proposed by mapping for {proposal.source_type}",
                           "auto_proposed": True},
                "approval_status": "pending",
                "auto_proposed": True,
                "proposed_by_source_id": (sample_ids or [None])[0],
                "proposal_rationale": proposal.rationale,
                "embedding": emb,
            },
            on_conflict="id",
        ).execute()
    for new_p in proposal.new_edge_types or []:
        if not new_p:
            continue
        emb = embed_text(new_p)
        db.table("edge_type_config").upsert(
            {
                "id": new_p,
                "config": {"description": f"Auto-proposed by mapping for {proposal.source_type}",
                           "auto_proposed": True},
                "approval_status": "pending",
                "auto_proposed": True,
                "proposed_by_source_id": (sample_ids or [None])[0],
                "proposal_rationale": proposal.rationale,
                "embedding": emb,
            },
            on_conflict="id",
        ).execute()
    return status


# ---------------------------------------------------------------------------
# Auto-approval gate
# ---------------------------------------------------------------------------


def should_auto_approve(
    proposal: MappingProposal,
    validation_stats: dict[str, Any],
) -> bool:
    """Hybrid rule: only mappings that purely reuse existing types AND validate
    cleanly skip the human inbox.
    """
    if proposal.new_entity_types or proposal.new_edge_types:
        return False
    if proposal.confidence < AUTO_APPROVE_CONFIDENCE:
        return False
    if validation_stats.get("entity_rate", 0) < AUTO_APPROVE_VALIDATION_RATE:
        return False
    return True


# ---------------------------------------------------------------------------
# Type-similarity helper (used by approval workflow)
# ---------------------------------------------------------------------------


def find_nearest_type(
    name: str,
    kind: Literal["entity", "edge"],
    db: Any,
) -> tuple[str | None, float | None]:
    """Return (closest_existing_id, distance). Distance is 1 - cosine_similarity."""
    emb = embed_text(name)
    if emb is None:
        return None, None
    table = "entity_type_config" if kind == "entity" else "edge_type_config"
    rows = (
        db.table(table)
        .select("id, embedding")
        .eq("approval_status", "approved")
        .execute()
        .data
        or []
    )
    if not rows:
        return None, None

    import math

    def cosine(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb) if na and nb else 0

    best_id, best_sim = None, -1.0
    for row in rows:
        their_emb = row.get("embedding")
        if not their_emb:
            continue
        sim = cosine(emb, their_emb)
        if sim > best_sim:
            best_sim = sim
            best_id = row["id"]
    if best_id is None:
        return None, None
    return best_id, 1.0 - best_sim
