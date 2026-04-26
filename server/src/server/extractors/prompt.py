"""Shared extraction prompt + closed-vocab predicate whitelist.

Used by both:
- server/scripts/gen_pioneer_training.py (Gemini-as-teacher synthetic data)
- server/src/server/extractors/gemini.py (production Gemini fallback)

Keeping them in one place is the only way to avoid silent drift between
the labels Pioneer trains on and the labels we evaluate against later.
"""

from __future__ import annotations

# Closed entity vocabulary. Pioneer's GLiNER2 schema lists exactly these.
ENTITY_TYPES: tuple[str, ...] = (
    "person",
    "customer",
    "product",
    "org_unit",
    "process",
    "policy",
    "project",
    "task",
    "ticket",
    "vendor",
    "repo",
)

# Closed predicate vocabulary. Each row: (predicate, subject_type, object_kind).
# `object_kind` is the type-name when object_type=entity, or a literal kind otherwise.
# Order matters for the prompt — we list them grouped by subject type.
PREDICATES: tuple[tuple[str, str, str], ...] = (
    # person ---
    ("title",            "person", "string"),
    ("department",       "person", "org_unit"),
    ("email",            "person", "string"),
    ("phone",            "person", "string"),
    ("located_in",       "person", "string"),
    ("reports_to",       "person", "person"),
    ("works_for",        "person", "org_unit"),
    ("sent_email_to",    "person", "person"),
    ("has_meeting_with", "person", "person"),
    # customer / vendor ---
    ("located_in",       "customer", "string"),
    ("account_manager",  "customer", "person"),
    ("located_in",       "vendor", "string"),
    # product ---
    ("belongs_to",       "product", "org_unit"),
    ("sold_to",          "product", "customer"),
    # org_unit ---
    ("managed_by",       "org_unit", "person"),
    ("located_in",       "org_unit", "string"),
    # project / task / ticket ---
    ("assigned_to",      "project", "person"),
    ("assigned_to",      "task", "person"),
    ("assigned_to",      "ticket", "person"),
    ("belongs_to",       "project", "org_unit"),
    ("belongs_to",       "task", "org_unit"),
    ("belongs_to",       "ticket", "org_unit"),
    ("status",           "task", "string"),
    ("status",           "ticket", "string"),
    # cross-cutting ---
    ("discusses",        "person", "string"),
    ("mentions",         "person", "string"),
)


def _format_predicate_block() -> str:
    grouped: dict[str, list[str]] = {}
    for pred, subj, obj_kind in PREDICATES:
        grouped.setdefault(subj, []).append(f"  - {pred:<18}({subj} → {obj_kind})")
    out: list[str] = []
    for subj_type, lines in grouped.items():
        out.append(f"{subj_type}:")
        out.extend(lines)
        out.append("")
    return "\n".join(out).rstrip()


EXTRACTION_PROMPT: str = f"""You extract a typed knowledge graph from one enterprise text chunk.

ENTITY TYPES (use only these for `type`):
- person     a named individual: employee, customer contact, etc. NOT a role or pronoun.
- customer   an external customer organization
- vendor     an external supplier or vendor organization
- product    a product, service, or offering
- org_unit   an internal department, team, business unit, or the company itself
- process    a recurring business process or workflow
- policy     a named company policy, rule, or guideline
- project    a named internal project or initiative
- task       a specific action item or assignment
- ticket     a support ticket, incident, or service request
- repo       a software repository or codebase

PREDICATE WHITELIST (use ONLY these for `predicate`; never invent new ones):
{_format_predicate_block()}

ENTITY IDS:
- Format: "<type>:<slug>"
- slug = canonical_name, lowercased, non-alphanumerics → "-", trimmed.
- "Jane Doe"        → "person:jane-doe"
- "Acme.co"         → "org_unit:acme-co"
- "MacBook Pro 16"  → "product:macbook-pro-16"

EXTRACTION RULES:
1. canonical_name is the form that should appear in a directory.
2. aliases = OTHER spellings/short-forms found in this chunk. Empty list if none.
3. Each fact's `subject` and (if object_type=entity) `object` MUST refer to entity ids you emit in this same response.
4. SKIP — do NOT extract as entities:
   - pronouns (he/she/we/us/they)
   - generic role nouns without a name ("the manager", "an employee")
   - email-signature boilerplate ("Best regards", "Sent from my iPhone")
   - URLs, file paths — they go in attributes
   - days of the week, times of day — they are qualifiers, not entities
5. If a chunk has nothing extractable (just headers or pleasantries), return empty arrays.

CONFIDENCE CALIBRATION:
- 1.0  explicitly stated  ("Jane Doe, HR Manager"               → title=HR Manager)
- 0.8  strongly implied   (signature shows title + department)
- 0.6  inferred           ("jane.doe@acme.com"                  → works_for acme, conf 0.6)
- skip if you would have to guess

EXAMPLE 1 (source_type: email):
Input:
"From: Jane Doe <jane.doe@acme.com>
Subject: HR Synergy
Hi Bob, scheduled meeting with Carol about employee retention.
Jane Doe, HR Manager, Acme.co, Berlin"

Output:
{{
  "entities": [
    {{"id": "person:jane-doe", "type": "person", "canonical_name": "Jane Doe", "aliases": [], "attributes": {{"email": "jane.doe@acme.com"}}}},
    {{"id": "person:bob", "type": "person", "canonical_name": "Bob", "aliases": []}},
    {{"id": "person:carol", "type": "person", "canonical_name": "Carol", "aliases": []}},
    {{"id": "org_unit:acme-co", "type": "org_unit", "canonical_name": "Acme.co", "aliases": []}}
  ],
  "facts": [
    {{"subject": "person:jane-doe", "predicate": "title",            "object": "HR Manager",         "object_type": "string", "confidence": 1.0}},
    {{"subject": "person:jane-doe", "predicate": "located_in",       "object": "Berlin",             "object_type": "string", "confidence": 1.0}},
    {{"subject": "person:jane-doe", "predicate": "works_for",        "object": "org_unit:acme-co",   "object_type": "entity", "confidence": 1.0}},
    {{"subject": "person:jane-doe", "predicate": "sent_email_to",    "object": "person:bob",         "object_type": "entity", "confidence": 1.0}},
    {{"subject": "person:jane-doe", "predicate": "has_meeting_with", "object": "person:carol",       "object_type": "entity", "confidence": 1.0}}
  ]
}}

EXAMPLE 2 (source_type: hr_record):
Input:
"Raj Patel is a Director in Engineering at the EN14 level. 12 years of software engineering experience leading cross-functional teams."

Output:
{{
  "entities": [
    {{"id": "person:raj-patel", "type": "person", "canonical_name": "Raj Patel", "aliases": []}},
    {{"id": "org_unit:engineering", "type": "org_unit", "canonical_name": "Engineering", "aliases": []}}
  ],
  "facts": [
    {{"subject": "person:raj-patel", "predicate": "title",      "object": "Director",            "object_type": "string", "confidence": 1.0}},
    {{"subject": "person:raj-patel", "predicate": "department", "object": "org_unit:engineering", "object_type": "entity", "confidence": 1.0}}
  ]
}}
"""
