# Data Model

Shared schemas across L1 → L3. This is the *contract* — design discussion first, implementation later.

See [team-briefing-technical.md](team-briefing-technical.md) for how the layers use these types.

## Overview

```
SourceRecord    raw, normalized input from one adapter
    │
    ▼
Entity          a thing in the company (person, customer, product, ...)
    │
    ▼
Fact            a claim about an Entity, with provenance
    │
    ▼
Resolution      a human decision on a conflict between Facts
```

## SourceRecord

The atomic unit of **input**. Everything above is derived from these.

```yaml
SourceRecord:
  id:              string         # stable: hash(source_type + source_native_id)
  source_type:     enum           # email | crm_contact | hr_record | policy_doc |
                                  # ticket | chat_message | meeting_note | ...
  source_uri:      string         # pointer to the raw artifact (file path, URL)
  source_native_id: string        # the source system's own ID (e.g. email Message-ID)
  payload:         object         # normalized fields, shape depends on source_type
  content_hash:    string         # sha256 of canonical JSON(payload)
  ingested_at:     timestamp
  superseded_by:   string?        # id of the SourceRecord that replaced this one
```

**Principles:**
- L1 never interprets. Just parse + normalize + hash + persist.
- `content_hash` drives change detection in L4. If hash differs from last seen → dependent facts must re-derive.
- Superseded records are kept (audit), not deleted.

**Example:**

```json
{
  "id": "email:sha256:abc123...",
  "source_type": "email",
  "source_uri": "data/raw/emails/2026-04-12-renewal-acme.eml",
  "source_native_id": "<CAK123@example.com>",
  "payload": {
    "from": "alice@company.com",
    "to": ["bob@acme.com"],
    "subject": "Acme renewal — pricing proposal",
    "body_text": "...",
    "sent_at": "2026-04-12T09:14:00Z",
    "attachments": []
  },
  "content_hash": "sha256:...",
  "ingested_at": "2026-04-25T10:03:00Z",
  "superseded_by": null
}
```

## Entity

A **thing** that exists in the company. Typed, named, has attributes, has aliases.

```yaml
Entity:
  id:              string         # "person:alice-schmidt", "customer:acme-gmbh"
  type:            enum           # person | customer | product | org_unit |
                                  # process | policy | project | task | ticket
  canonical_name:  string         # "Alice Schmidt"
  aliases:         string[]       # ["Alice S.", "a.schmidt", "Lise"]
  attributes:      object         # type-dependent: {email, title, role, ...}
  status:          enum           # live | draft | archived
  created_at:      timestamp
  updated_at:      timestamp
  provenance:      string[]       # SourceRecord.id[] — where this entity was seen
  embedding:       float[]?       # cached embedding of canonical_name + key attrs
```

**Principles:**
- `id` is stable once assigned. Aliases grow over time.
- `type` governs allowed `attributes` keys (soft-validated, extensible).
- Entity resolution (merging "Alice S." and "Alice Schmidt") = L2 logic; produces a canonical entity with expanded `aliases` and combined `provenance`.

**Example:**

```json
{
  "id": "person:alice-schmidt",
  "type": "person",
  "canonical_name": "Alice Schmidt",
  "aliases": ["Alice S.", "a.schmidt", "Alice from Sales"],
  "attributes": {
    "email": "alice@company.com",
    "title": "Senior Account Manager",
    "department": "Sales",
    "employee_id": "E-0142"
  },
  "status": "live",
  "created_at": "2026-04-25T10:03:00Z",
  "updated_at": "2026-04-25T10:03:00Z",
  "provenance": [
    "hr_record:sha256:...",
    "email:sha256:abc123...",
    "crm_contact:sha256:..."
  ]
}
```

## Fact

A **reified relation** about an Entity. The atomic unit of the memory. **Provenance lives here, not on entities.**

```yaml
Fact:
  id:              string         # "fact:<hash>"
  subject:         string         # Entity.id
  predicate:       string         # "account_manager_of", "renewal_date",
                                  # "reports_to", "volume_eur", "status"
  object:          Entity.id | literal  # another Entity, or a scalar value
  object_type:     enum           # entity | string | number | date | bool | enum
  confidence:      float          # 0..1, from the extractor that produced it
  status:          enum           # live | draft | superseded | disputed
  derived_from:    string[]       # SourceRecord.id[] — which sources support this fact
  last_hash_seen:  object         # { [source_id]: content_hash } for change detection
  qualifiers:      object         # {valid_from, valid_to, context, ...}
  created_at:      timestamp
  updated_at:      timestamp
  superseded_by:   string?        # id of Fact that replaced this one
  embedding:       float[]?       # embedding of the verbalized form
```

**Principles:**
- **Fact-level provenance.** Each `derived_from` entry + `last_hash_seen` together let us re-derive the fact when any source changes.
- **Reification.** Storing relations as first-class nodes (not just graph edges) lets us attach metadata (confidence, status, qualifiers) to any relation.
- **Confidence drives retrieval.** `search_memory` filters on `confidence >= threshold` by default.
- **`status: disputed`** = active conflict, waiting for L4 resolution. Retrieval includes it but flags it.

**Example — simple fact:**

```json
{
  "id": "fact:sha256:...",
  "subject": "customer:acme-gmbh",
  "predicate": "account_manager_of",
  "object": "person:alice-schmidt",
  "object_type": "entity",
  "confidence": 1.0,
  "status": "live",
  "derived_from": ["hr_record:sha256:...", "crm_contact:sha256:..."],
  "last_hash_seen": {
    "hr_record:sha256:...": "sha256:hr-hash-1",
    "crm_contact:sha256:...": "sha256:crm-hash-1"
  },
  "qualifiers": {"valid_from": "2025-09-01"},
  "created_at": "2026-04-25T10:03:00Z",
  "updated_at": "2026-04-25T10:03:00Z"
}
```

**Example — conflicted fact:**

```json
{
  "id": "fact:sha256:...",
  "subject": "customer:acme-gmbh",
  "predicate": "renewal_date",
  "object": "2026-06-15",
  "object_type": "date",
  "confidence": 0.85,
  "status": "disputed",
  "derived_from": ["email:sha256:abc123...", "crm_contact:sha256:def456..."],
  "last_hash_seen": {...},
  "qualifiers": {},
  "created_at": "2026-04-25T10:03:00Z",
  "updated_at": "2026-04-25T10:10:00Z"
}
```

The "disputed" Fact co-exists with another Fact claiming a different `renewal_date` — both share the same `(subject, predicate)` but differ on `object`. The Ambiguity Inbox surfaces this pair.

## Resolution

A human decision that resolves a conflict between Facts. Written back as a `SourceRecord(type=human_resolution)` so it's itself auditable and survives re-runs.

```yaml
Resolution:
  id:              string
  conflict_facts:  string[]       # Fact.id[] involved in the conflict
  decision:        enum           # pick_one | merge | both_with_qualifier | reject_all
  chosen_fact_id:  string?        # if decision == pick_one
  qualifier_added: object?        # if decision == both_with_qualifier, e.g. {context: "EMEA vs US"}
  rationale:       string         # free-text from the human
  resolved_by:     string         # user ID
  resolved_at:     timestamp
```

The Resolution is **also** persisted as a `SourceRecord`:

```json
{
  "id": "human_resolution:sha256:...",
  "source_type": "human_resolution",
  "source_uri": "internal:resolution/<id>",
  "payload": {<Resolution object>},
  "content_hash": "sha256:...",
  "ingested_at": "..."
}
```

That way, future L2 re-runs see "a human already decided X" and respect it.

## Virtual File System projection

VFS files are **rendered views** of subgraphs. They are not source-of-truth.

```
/static/
  people/
    alice-schmidt.md
  customers/
    acme-gmbh.md
  products/
    ...
/procedural/
  policies/
    contract-approval.md
  sops/
    ...
/trajectory/
  projects/
    acme-renewal-2026.md
  tasks/
    ...
  incidents/
    ...
```

Each `.md` file has:

```markdown
---
entity_id: customer:acme-gmbh
type: customer
facts:
  - predicate: account_manager_of
    object: person:alice-schmidt
    source: hr_record:abc
    confidence: 1.0
  - predicate: renewal_date
    object: "2026-06-15"
    source: email:abc123
    confidence: 0.85
    status: disputed
---

# Acme GmbH

## Summary

Customer since 2021. Currently in renewal negotiation for 2026...

## Facts

- **Account Manager:** [Alice Schmidt](../people/alice-schmidt.md) [†source](provenance://hr_record:abc)
- **Renewal Date:** 2026-06-15 ⚠️ disputed [†source1](provenance://email:abc) [†source2](provenance://crm:def)
- **Volume:** 150,000 EUR [†source](provenance://email:xyz)

## Open items

- [Ticket: price adjustment request](../../trajectory/tasks/ticket-55.md)
- [Project: Acme Renewal 2026](../../trajectory/projects/acme-renewal-2026.md)

## References

- [hr_record:E-0142](provenance://...)
- [crm_contact:acme-gmbh](provenance://...)
- [email:2026-04-12 Acme renewal pricing](provenance://...)
```

Files regenerate deterministically from the graph. If the human edits a file in the UI, the diff is parsed back into `propose_fact` / `propose_resolution` calls — the file itself never becomes a source of truth.

## ID conventions

- Entity: `{type}:{slug}` → `person:alice-schmidt`, `customer:acme-gmbh`
- SourceRecord: `{source_type}:sha256:{content_hash}` → `email:sha256:abc...`
- Fact: `fact:sha256:{hash_of(subject, predicate, object, derived_from)}`
- Resolution: `resolution:sha256:{hash}`

Deterministic IDs mean re-ingesting the same source produces the same ID — idempotent.

## What's NOT in the model

Intentionally left out for simplicity (can be added Day 2 if needed):

- **Versions/history** on Facts → we use `superseded_by` linked lists, no branching history.
- **ACL / permissions** → out of scope for hack.
- **Multi-tenant** → single-company assumption.
- **Time-travel queries** → `qualifiers.valid_from/valid_to` is enough for the demo.
