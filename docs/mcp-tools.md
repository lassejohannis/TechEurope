# MCP Tools — Agent Surface

The MCP server is the **single way AI agents interact with the context base**. Five tools. No direct DB access, no raw RAG — everything goes through typed facts with provenance.

See [data-model.md](data-model.md) for the shapes referenced below.

## Tool overview

| # | Tool | Read/Write | Purpose |
|---|---|---|---|
| 1 | `search_memory` | read | Natural-language or keyword query → ranked facts + entities |
| 2 | `get_entity` | read | Full card for one entity (all live facts + sources) |
| 3 | `get_fact` | read | One fact with full provenance trail (source records + hashes) |
| 4 | `list_recent_changes` | read | Diff since timestamp (new / superseded / disputed facts) |
| 5 | `propose_fact` | write | Agent submits a new fact; auto-merge or escalate to HITL |

## 1. `search_memory`

### Input

```typescript
{
  query: string,            // natural language OR keyword
  k?: number,               // max results, default 20
  filter?: {
    entity_types?: string[],     // ["customer", "person"]
    predicates?: string[],       // ["renewal_date", "account_manager_of"]
    min_confidence?: number,     // 0..1, default 0.5
    status?: ("live" | "disputed" | "draft")[],  // default ["live", "disputed"]
    updated_since?: string       // ISO timestamp
  }
}
```

### Output

```typescript
{
  entities: Entity[],       // directly-matched entities (canonical + alias hits)
  facts: Fact[],            // ranked facts incl. graph-expanded 1–2 hop neighbors
  files: {                  // VFS file paths that match via BM25
    path: string,
    snippet: string,
    entity_id: string
  }[],
  query_interpretation: {   // what we thought the query meant (debug aid)
    entities_mentioned: string[],
    predicates_mentioned: string[],
    intent: "lookup" | "question" | "browse"
  }
}
```

### Example

**Call:**
```json
{
  "query": "what's the status of the acme renewal",
  "filter": { "min_confidence": 0.7 }
}
```

**Response:**
```json
{
  "entities": [
    { "id": "customer:acme-gmbh", "canonical_name": "Acme GmbH", "type": "customer" }
  ],
  "facts": [
    {
      "id": "fact:...",
      "subject": "customer:acme-gmbh",
      "predicate": "renewal_date",
      "object": "2026-06-15",
      "confidence": 0.85,
      "status": "disputed",
      "derived_from": ["email:abc", "crm:def"]
    },
    {
      "id": "fact:...",
      "subject": "customer:acme-gmbh",
      "predicate": "account_manager_of",
      "object": "person:alice-schmidt",
      "confidence": 1.0,
      "status": "live",
      "derived_from": ["hr:xyz"]
    }
  ],
  "files": [
    {
      "path": "/static/customers/acme-gmbh.md",
      "snippet": "...Currently in renewal negotiation...",
      "entity_id": "customer:acme-gmbh"
    }
  ],
  "query_interpretation": {
    "entities_mentioned": ["acme"],
    "predicates_mentioned": ["status", "renewal"],
    "intent": "question"
  }
}
```

### Retrieval pipeline inside the tool

See [team-briefing-technical.md](team-briefing-technical.md) for the canonical engineering plan. Short version of the retrieval pipeline inside `search_memory`:

1. Parse query → detect entity names, predicates, intent
2. Fan out: exact entity match + vector search on entity embeddings + vector search on fact embeddings + BM25 on VFS files
3. Graph-expand seed entities (1–2 hops) via NetworkX
4. Merge, dedupe, filter by `status` / `min_confidence`
5. Rank by `relevance × confidence × recency`
6. Return top-`k`

## 2. `get_entity`

### Input

```typescript
{
  entity_id: string,            // e.g. "customer:acme-gmbh"
  include_superseded?: boolean, // default false
  fact_types?: string[]         // optional filter on predicates
}
```

### Output

```typescript
{
  entity: Entity,
  facts: Fact[],                // all live facts where subject == entity_id
  inbound_facts: Fact[],        // facts where object == entity_id (who points TO this?)
  related_entities: {
    entity: Entity,
    via_predicate: string,
    via_fact_id: string
  }[],                          // 1-hop graph neighbors
  vfs_path: string              // "/static/customers/acme-gmbh.md"
}
```

### Example

**Call:** `{ "entity_id": "customer:acme-gmbh" }`

**Response:** full "customer card" — all known facts, who the AM is, which projects are open, which tickets are pending, pointer to the VFS file for a human view.

## 3. `get_fact`

### Input

```typescript
{
  fact_id: string,
  with_provenance?: boolean     // default true
}
```

### Output

```typescript
{
  fact: Fact,
  provenance: {
    source_record: SourceRecord,       // the raw record
    evidence_snippet: string,          // which field/sentence in the source supported this fact
    extractor: "rule" | "pioneer" | "gemini" | "human",
    extracted_at: string
  }[],
  conflicts?: Fact[]              // if fact.status == "disputed", the other side(s)
  supersedes?: string,            // prior Fact.id this one replaced
  superseded_by?: string
}
```

### Example — agent follows provenance

Agent sees `renewal_date: 2026-06-15` in a `search_memory` result. Wants to know why we believe it. Calls `get_fact(id)` → gets back the source emails + the exact sentence ("renewal expected mid-June '26") that produced the fact. Can cite that sentence in its reply.

## 4. `list_recent_changes`

### Input

```typescript
{
  since: string,                  // ISO timestamp
  entity_ids?: string[],          // filter to these entities
  kinds?: ("created" | "updated" | "superseded" | "disputed" | "resolved")[]
}
```

### Output

```typescript
{
  changes: {
    kind: "created" | "updated" | "superseded" | "disputed" | "resolved",
    fact_id: string,
    entity_id: string,
    old_value?: any,
    new_value: any,
    triggered_by: string,        // SourceRecord.id that caused the change
    at: string                   // ISO timestamp
  }[],
  cursor?: string                 // for pagination on large time windows
}
```

### Example — agent polls for updates

Background agent subscribed to Acme's status. Polls every 5 min:

```json
{ "since": "2026-04-25T10:00:00Z", "entity_ids": ["customer:acme-gmbh"] }
```

Gets back: `renewal_status` moved from `negotiating` → `accepted`, triggered by `email:latest`. Agent posts to Slack.

## 5. `propose_fact`

### Input

```typescript
{
  subject: string,              // Entity.id (or "new:person:alice-new" for new entity)
  predicate: string,
  object: string | number | boolean | null,
  object_type: "entity" | "string" | "number" | "date" | "bool" | "enum",
  confidence: number,           // 0..1 — the agent's own confidence
  source: {                     // attribution — where did the agent get this?
    kind: "agent_output" | "external_api" | "user_input_via_agent",
    description: string,        // free-text, e.g. "synthesized from email thread X"
    ref?: string                // optional URI
  },
  qualifiers?: object
}
```

### Output

```typescript
{
  status: "accepted" | "duplicate" | "escalated" | "rejected",
  fact_id?: string,             // set if accepted / duplicate
  reason: string,               // human-readable
  escalated_to?: {              // set if status == "escalated"
    inbox_item_id: string,      // in Entire HITL queue
    conflict_with: string[]     // existing Fact.id[]
  }
}
```

### Decision logic (server-side)

```
if (subject, predicate, object) already exists as live Fact:
    → status: "duplicate", add agent source to provenance, return existing fact_id

elif (subject, predicate) exists with different object, confidence > 0.8:
    → status: "escalated", create Ambiguity Inbox item, return

elif (subject, predicate) exists with different object, confidence <= 0.8:
    → status: "rejected", reason: "lower confidence than existing fact"

else (fresh assertion):
    if confidence >= 0.8: accept → new Fact(status=live)
    else: accept → new Fact(status=draft)
```

### Example — agent writes back after reading an email

```json
{
  "subject": "customer:acme-gmbh",
  "predicate": "renewal_status",
  "object": "accepted",
  "object_type": "enum",
  "confidence": 0.9,
  "source": {
    "kind": "agent_output",
    "description": "extracted from email 'Acme renewal — pricing proposal' (agent run 2026-04-25T11:30)",
    "ref": "email:sha256:newest"
  }
}
```

Response:
```json
{
  "status": "accepted",
  "fact_id": "fact:...",
  "reason": "New assertion, confidence 0.9, no conflict"
}
```

## Error model

All tools return HTTP 200 (or MCP success) with a discriminated union on `status` — no exceptions for normal flow. Only infra errors (DB down, Qdrant unreachable) return an actual error response.

## Open questions for the team

1. **Do we need a 6th tool for batch proposals?** Agent processing an email thread may want to submit 20 facts atomically.
2. **`search_memory` query interpretation** — should we expose an "explain" mode that shows the fan-out hits before ranking, for debugging / transparency in the jury demo?
3. **Write permissions** — can any MCP caller `propose_fact`, or do we gate it on an API key? For the demo, probably everyone; for "production readiness" narrative, mention we'd scope per-agent.
4. **`get_entity` inbound_facts depth** — 1 hop only, or configurable? Too wide and we drown the agent; too narrow and we lose context.
