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
import re
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


# Common nouns that NER (Pioneer/GLiNER2) routinely mis-labels as proper-noun
# entities. These are not real people/orgs — they're substrings of the
# extraction text that happened to be capitalized or pattern-matched.
# NOTE: We deliberately DON'T include "invoice" — there is a legit document
# entity named "Invoice" in some CRM datasets.
_BAD_NAME_LITERALS: frozenset[str] = frozenset({
    "policy", "document", "email", "communication", "complaint", "complainant",
    "violation", "violations", "subject", "report", "guideline", "guidelines",
    "compliance", "employees", "managers", "engineers", "developers", "members",
    "team", "department", "company", "organization", "person", "user",
    "data", "information", "records", "record",
})

# Plural-person suffixes Pioneer often labels as `person`.
_PLURAL_PERSON_SUFFIXES: tuple[str, ...] = (
    "employees", "engineers", "managers", "developers", "members",
    "users", "operators", "officers", "stakeholders", "team",
)

# Real HTML entities either terminate with `;` (e.g. `&amp;`, `&nbsp;`) or
# are unterminated remnants from sloppy PDF extraction (e.g. "Legal &amp",
# trailing). We deliberately do NOT match `&I` in "D&I Training".
_HTML_ENTITY_RE = re.compile(
    r"&(?:amp|nbsp|lt|gt|quot|apos|#\d+);?(?:\s|$)", re.IGNORECASE
)


# Common nouns / domain words. A multi-word `person` whose every word is in
# this set (e.g. "Information Security Policy", "Hardware Assets") is almost
# certainly a Pioneer mislabel — real person names contain proper nouns.
_COMMON_NOUNS_FOR_PERSON_CHECK: frozenset[str] = frozenset({
    # generic
    "information", "data", "system", "systems", "service", "services",
    "process", "processes", "report", "reports", "record", "records",
    "asset", "assets", "resource", "resources", "tool", "tools",
    "user", "users", "team", "teams", "group", "groups",
    # security / compliance
    "security", "policy", "policies", "compliance", "audit", "audits",
    "risk", "risks", "control", "controls", "violation", "violations",
    "incident", "incidents", "threat", "threats", "vulnerability",
    # tech
    "hardware", "software", "network", "device", "devices", "server",
    "database", "application", "platform", "infrastructure",
    "code", "configuration", "technology", "technologies",
    # business
    "company", "department", "division", "office", "branch",
    "project", "program", "initiative", "campaign", "operation",
    # common modifiers
    "new", "old", "primary", "secondary", "general", "specific",
    "internal", "external", "global", "local", "annual", "quarterly",
})


def _is_pseudo_entity(entity_type: str, name: str) -> bool:
    """True if (type, name) is almost certainly a NER false positive.

    Conservative — only blocks shapes we've actually seen polluting the DB:
    - too short / too long (per-type limits)
    - known common-noun literals
    - HTML-entity remnants from PDF extraction
    - plural-person suffixes mis-labeled as person
    - synthetic HR-code shapes (`emp_NNNN`)
    - person-typed names not starting with a letter
    """
    n = (name or "").strip()
    if not n:
        return True

    # Per-type length limits. Communication/document/product names can be
    # long; org names can be short ("HR"); only person is strict.
    min_len, max_len = 2, 80
    if entity_type == "person":
        min_len, max_len = 3, 80
    elif entity_type in ("communication", "document", "product"):
        min_len, max_len = 2, 250

    if len(n) < min_len or len(n) > max_len:
        return True

    low = n.lower()
    if low in _BAD_NAME_LITERALS:
        return True
    if _HTML_ENTITY_RE.search(n):
        return True
    if entity_type == "person":
        if low.endswith(_PLURAL_PERSON_SUFFIXES):
            return True
        # `emp_NNNN`-style HR codes — synthetic IDs that never got resolved
        # to a real name. Filter these out so they don't pollute the graph.
        if re.fullmatch(r"emp[_-]?\d{2,}", low):
            return True
        # Names starting with a digit or non-letter — not a real person name.
        if not n[0].isalpha():
            return True
        # Multi-word names where every word is a generic noun (e.g.
        # "Information Security Policy", "Hardware Assets"). Real person
        # names contain at least one proper-noun-like token.
        words = re.findall(r"[A-Za-z]+", low)
        if len(words) >= 2 and all(w in _COMMON_NOUNS_FOR_PERSON_CHECK for w in words):
            return True
    return False


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

    # A fact without any resolved object is not a real fact — the mapping
    # referenced a field the payload doesn't contain. Drop it so the validator
    # scores honestly instead of inflating fact_rate to 1.00.
    if object_key is None and object_literal is None:
        return None

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
    if not mapping:
        logger.debug("no mapping for source_type=%s", source_type)
        return [], []
    if mapping.get("status") not in ("approved", "pending"):
        logger.debug(
            "skipping mapping for %s with status=%s",
            source_type,
            mapping.get("status"),
        )
        return [], []

    entities, facts = apply_mapping(source_record, mapping["config"] or {})

    # Free-text LLM extract for opted-in records (Phase D of the resolver plan).
    # If the mapping declares free_text_paths, use them. Otherwise auto-detect:
    # any top-level string field longer than 200 chars is a candidate for Pioneer.
    cfg = mapping["config"] or {}
    declared = list(cfg.get("free_text_paths") or [])
    paths = list(declared)
    # Always also probe long top-level string fields the LLM may have missed
    # (e.g. `$.text` on PDFs when Gemini guessed `$.body`).
    declared_keys = {p.lstrip("$.").split(".")[0] for p in declared}
    for key, val in (source_record.get("payload") or {}).items():
        if key in declared_keys:
            continue
        if isinstance(val, str) and len(val) >= 200:
            paths.append(f"$.{key}")
    if llm_extract and paths:
        try:
            raw_facts = _llm_free_text_facts(source_record, paths, cfg)
            # Drop facts whose subject is a pseudo-entity outright. If only the
            # object is pseudo, downgrade to a literal-only fact when possible
            # so the predicate is still captured without polluting the graph.
            new_facts: list[PendingFact] = []
            for f in raw_facts:
                if _is_pseudo_entity(f.subject_key[0], f.subject_key[1]):
                    continue
                if f.object_key and _is_pseudo_entity(f.object_key[0], f.object_key[1]):
                    if f.object_literal is None:
                        # No literal fallback available → drop the fact.
                        continue
                    f.object_key = None
                new_facts.append(f)

            # Materialize subject/object entities Pioneer/Gemini emitted so the
            # downstream `_persist_fact` lookup in name_to_id finds them.
            seen_keys = {(e.entity_type, e.canonical_name) for e in entities}
            for f in new_facts:
                for key in (f.subject_key, f.object_key):
                    if key is None:
                        continue
                    if key in seen_keys:
                        continue
                    if key[0] in FORBIDDEN_ENTITY_TYPES:
                        continue
                    if _is_pseudo_entity(key[0], key[1]):
                        continue
                    entities.append(
                        CandidateEntity(
                            canonical_name=key[1],
                            entity_type=key[0],
                            attrs={},
                            source_id=source_record.get("id", ""),
                        )
                    )
                    seen_keys.add(key)
            facts.extend(new_facts)
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
