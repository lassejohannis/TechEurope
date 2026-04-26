"""Generic config-driven extraction engine.

Replaces the hardcoded ``resolver/extract.py`` per-source-type Python
functions. Reads a JSONata mapping config from ``source_type_mapping`` and
applies it to a source_record's payload, emitting CandidateEntities and
PendingFacts that the existing resolver/cli pipeline already understands.

A mapping config has this shape:

```json
{
  "entities": [
    {
      "type": "person",
      "canonical_name": "$lowercase(reporter.display_name)",
      "hard_ids": {
        "email": "reporter.email",
        "domain": "$substringAfter(reporter.email, '@')"
      },
      "extra_attrs": {"role": "reporter"}
    }
  ],
  "facts": [
    {
      "subject_canonical_name": "$lowercase(reporter.display_name)",
      "subject_type": "person",
      "predicate": "created",
      "object_canonical_name": "summary",
      "object_type": "communication",
      "confidence": 0.9
    }
  ],
  "free_text_paths": ["description", "comments[*].body"]
}
```

The engine never raises on bad config — it just produces fewer entities
or facts. Validation happens during inference (Phase G) before approval.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable

from server.ontology.jsonata_eval import jeval, jstr
from server.resolver.cascade import CandidateEntity
from server.resolver.extract import PendingFact

logger = logging.getLogger(__name__)


# Pseudo-types Gemini sometimes emits when it conflates "primitive value"
# with "entity type". These should never become entities — they're scalar
# values, not first-class graph nodes. Filtered both at mapping-approve
# time (cli.py) and at runtime (apply_mapping below) for defense-in-depth.
FORBIDDEN_ENTITY_TYPES = frozenset({
    "string", "str", "text",
    "number", "integer", "int", "float", "decimal",
    "bool", "boolean",
    "date", "datetime", "time", "timestamp",
    "any", "null", "none", "object", "array", "list", "dict",
    "value",
})


def _compact_canonical_name(name: str, entity_type: str) -> str:
    """Trim very-long canonical_names for free-text-y entity types.

    Some Gemini-inferred mappings (e.g. collaboration chats) bind
    `canonical_name` to the full message body, producing 1–2k char names
    that bloat embeddings, make IDs unreadable, and inflate the inbox
    diff display. For document/communication, prefer the first sentence
    or first 117 chars + ellipsis.
    """
    if entity_type not in {"document", "communication"}:
        return name
    name = name.strip()
    if len(name) <= 120:
        return name
    for sep in (". ", "? ", "! ", "\n\n", "\n"):
        idx = name.find(sep, 20, 200)
        if idx > 0:
            return name[: idx + 1].strip()
    return name[:117].rstrip() + "..."


def apply_mapping(
    record: dict[str, Any],
    config: dict[str, Any],
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    """Apply a JSONata mapping config to a source_records payload.

    ``record`` is the full source_records row (we read ``record['payload']``).
    ``config`` is the JSONata mapping (the ``config`` jsonb of source_type_mapping).
    """
    payload = record.get("payload") or {}
    sid = record.get("id", "") or ""

    entities: list[CandidateEntity] = []
    facts: list[PendingFact] = []

    for spec in config.get("entities") or []:
        cand = _entity_from_spec(spec, payload, source_id=sid)
        if cand is not None:
            entities.append(cand)

    for spec in config.get("facts") or []:
        pf = _fact_from_spec(spec, payload)
        if pf is not None:
            facts.append(pf)

    return entities, facts


def _entity_from_spec(
    spec: dict[str, Any], payload: dict[str, Any], source_id: str
) -> CandidateEntity | None:
    canonical_name = jstr(spec.get("canonical_name"), payload)
    if not canonical_name:
        return None

    entity_type = spec.get("type")
    if not entity_type:
        return None
    if str(entity_type).strip().lower() in FORBIDDEN_ENTITY_TYPES:
        # Gemini occasionally proposes scalar pseudo-types as entities (e.g.
        # type="string"). Drop them silently — they belong as object_literal,
        # not as graph nodes.
        return None

    attrs: dict[str, Any] = {}

    hard_ids = spec.get("hard_ids") or {}
    for key, expr in hard_ids.items():
        val = jstr(expr, payload)
        if val:
            attrs[key] = val

    extra = spec.get("extra_attrs") or {}
    for key, expr_or_literal in extra.items():
        # Strings starting with $ or containing JSONata operators are evaluated;
        # plain literals are stored verbatim.
        if isinstance(expr_or_literal, str) and (
            expr_or_literal.startswith("$") or "." in expr_or_literal
        ):
            val = jeval(expr_or_literal, payload)
            if val is not None:
                attrs[key] = val
        else:
            attrs[key] = expr_or_literal

    canonical_name = _compact_canonical_name(canonical_name, str(entity_type))

    cand = CandidateEntity(
        entity_type=str(entity_type),
        canonical_name=canonical_name,
        attrs=attrs,
        source_id=source_id,
    )
    return cand


def _fact_from_spec(spec: dict[str, Any], payload: dict[str, Any]) -> PendingFact | None:
    predicate = spec.get("predicate")
    if not predicate:
        return None

    subject_name = jstr(spec.get("subject_canonical_name"), payload)
    subject_type = spec.get("subject_type")
    if not subject_name or not subject_type:
        return None

    object_name = jstr(spec.get("object_canonical_name"), payload)
    object_type = spec.get("object_type")
    object_literal_expr = spec.get("object_literal")

    object_key: tuple[str, str] | None = None
    object_literal: Any | None = None

    if object_name and object_type:
        object_key = (str(object_type), object_name)
    elif object_literal_expr:
        val = jeval(object_literal_expr, payload)
        if val is not None:
            object_literal = val if isinstance(val, (dict, list)) else {"value": val}

    extraction_method = str(spec.get("extraction_method") or "rule")
    confidence = spec.get("confidence")
    if isinstance(confidence, (int, float)):
        confidence_value = max(0.0, min(1.0, float(confidence)))
    else:
        confidence_value = _default_fact_confidence(
            predicate=str(predicate),
            extraction_method=extraction_method,
            has_entity_object=object_key is not None,
            has_literal_object=object_literal is not None,
        )

    return PendingFact(
        subject_key=(str(subject_type), subject_name),
        predicate=str(predicate),
        object_key=object_key,
        object_literal=object_literal,
        confidence=confidence_value,
        extraction_method=extraction_method,
    )


def _default_fact_confidence(
    *,
    predicate: str,
    extraction_method: str,
    has_entity_object: bool,
    has_literal_object: bool,
) -> float:
    """Derive a default confidence when mapping doesn't set one.

    This avoids collapsing too many facts at a single 0.85 value.
    """
    high_precision_predicates = {
        "email",
        "emp_id",
        "employee_id",
        "tax_id",
        "domain",
        "sku",
        "product_id",
    }
    if predicate in high_precision_predicates:
        return 0.95
    if extraction_method == "human":
        return 0.95
    if has_entity_object:
        return 0.90
    if has_literal_object:
        return 0.78
    return 0.72


# ---------------------------------------------------------------------------
# Resolve-time entrypoint
# ---------------------------------------------------------------------------


def resolve_with_engine(
    source_record: dict[str, Any],
    db: Any,
    *,
    llm_extract: bool = False,
) -> tuple[list[CandidateEntity], list[PendingFact]]:
    """Resolve a single source_record using its source_type_mapping.

    If no approved mapping exists, returns ([], []) and logs a warning.
    Caller may choose to invoke the AI proposer separately.
    """
    source_type = source_record.get("source_type") or ""
    if not source_type:
        return [], []

    mapping_row = (
        db.table("source_type_mapping")
        .select("config, status")
        .eq("source_type", source_type)
        .single()
        .execute()
    )
    mapping = mapping_row.data if hasattr(mapping_row, "data") else None
    if not mapping or mapping.get("status") != "approved":
        logger.debug(
            "no approved mapping for source_type=%s (status=%s)",
            source_type,
            (mapping or {}).get("status"),
        )
        return [], []

    entities, facts = apply_mapping(source_record, mapping["config"] or {})

    # Free-text LLM extract for opted-in records (Phase D of the resolver plan).
    if llm_extract and (paths := (mapping["config"] or {}).get("free_text_paths")):
        try:
            facts.extend(_llm_free_text_facts(source_record, paths, mapping["config"]))
        except Exception as exc:
            logger.debug("free_text extract failed: %s", exc)

    return entities, facts


def _llm_free_text_facts(
    source_record: dict[str, Any],
    paths: Iterable[str],
    mapping_config: dict[str, Any],
) -> list[PendingFact]:
    """Mine each free-text path for relationship facts.

    Strategy: try Pioneer (fine-tuned GLiNER2, ~700ms p50) first. If
    Pioneer is not configured, returns no result, or errors, fall back
    to Gemini's structured-output extractor (`extract_email_facts`,
    ~5s p50). Each emitted fact carries the extractor name in
    `extraction_method` so the demo can show the split per-record.
    """
    from server.extractors import pioneer
    from server.extractors.gemini_structured import extract_email_facts

    payload = source_record.get("payload") or {}
    facts: list[PendingFact] = []

    sender_name = jstr(mapping_config.get("free_text_sender"), payload) or ""
    recipient_name = jstr(mapping_config.get("free_text_recipient"), payload) or ""
    source_type = source_record.get("source_type") or "unknown"

    for path in paths:
        body = jstr(path, payload) or ""
        if len(body) < 200:
            continue

        # Pioneer-first: produces relations directly between named entities.
        if pioneer.AVAILABLE:
            pio_result = pioneer.extract(body, source_type=source_type)
            if pio_result and pio_result.facts:
                for pf in pio_result.facts:
                    object_key: tuple[str, str] | None = None
                    object_literal: dict[str, Any] | None = None
                    if pf.object_type == "entity" and isinstance(pf.object, str):
                        # Pioneer-emitted IDs are "<type>:<slug>" — split for the
                        # cascade's name-keyed lookup. Fall back to literal if
                        # the object isn't a recognized id shape.
                        if ":" in pf.object:
                            otype, oname = pf.object.split(":", 1)
                            object_key = (otype, oname.replace("-", " ").title())
                        else:
                            object_literal = {"value": pf.object}
                    else:
                        object_literal = {"value": pf.object}

                    if isinstance(pf.subject, str) and ":" in pf.subject:
                        stype, sname = pf.subject.split(":", 1)
                        subject_key: tuple[str, str] = (
                            stype,
                            sname.replace("-", " ").title(),
                        )
                    else:
                        subject_key = ("person", str(pf.subject))

                    facts.append(
                        PendingFact(
                            subject_key=subject_key,
                            predicate=pf.predicate,
                            object_key=object_key,
                            object_literal=object_literal,
                            confidence=float(pf.confidence),
                            extraction_method="pioneer",
                        )
                    )
                # Pioneer succeeded — skip Gemini for this body.
                continue

        # Gemini fallback (also runs when Pioneer is unavailable or returned empty).
        for ef in extract_email_facts(body, sender_name, recipient_name):
            object_key = ("person", ef.object_name.strip()) if ef.object_name else None
            object_literal = None if ef.object_name else {"quote": ef.quote}
            facts.append(
                PendingFact(
                    subject_key=("person", ef.subject_name.strip() or sender_name),
                    predicate=ef.predicate,
                    object_key=object_key,
                    object_literal=object_literal,
                    confidence=float(ef.confidence),
                    extraction_method="gemini",
                )
            )
    return facts
