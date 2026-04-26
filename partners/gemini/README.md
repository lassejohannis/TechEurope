# Gemini (Google DeepMind)

Gemini powers more code paths in this project than any other partner: embeddings, autonomous mapping inference, and structured extraction.

## What we use it for

Three completely separate use-cases, three different models:

1. **Embeddings for kNN** (`text-embedding-004`, 768 dim) — every entity gets an embedding stored in `entities.embedding` (pgvector HNSW). Used by Tier 3 of the resolution cascade.
2. **Autonomous mapping inference** (`gemini-2.5-flash`) — given 5 sample payloads from a new source-type, Gemini designs a JSONata-based extraction config (entities + facts) that we then validate on a hold-out sample.
3. **PDF multimodal extraction** (`gemini-2.5-pro`) — Wired but currently disabled at ingest time after we removed the `gemini_extract_invoice()` call from the invoice connector to fix a 17-min-stuck pipeline. The capability survives in `extractors/gemini_structured.py` for resolve-time use.

## How it's wired in

```
Connector.normalize() → SourceRecord
                         ↓
                 source_records (Postgres)
                         ↓
                  resolve CLI command
                         ↓
   ┌─────────────────────┼─────────────────────┐
   │                     │                     │
   ↓                     ↓                     ↓
apply_mapping     embed_text(name)     _llm_free_text_facts
(JSONata using     (text-embedding-004    (Pioneer-first; Gemini
 the inferred       per entity)           fallback for relation
 config)                                  extraction)
   │                     │                     │
   ↓                     ↓                     ↓
CandidateEntity     entities.embedding   PendingFact (relation)
```

Mapping inference runs off-line via `infer-source-mappings`. It builds a prompt from sample payloads + already-approved entity/edge types (so Gemini reuses the existing ontology where possible), gets a structured `MappingProposal` back via `response_schema`, validates it on hold-out samples, and either auto-approves or routes to a HITL inbox.

## Code paths

- `server/src/server/extractors/gemini_structured.py` — `gemini_extract_invoice`, `extract_email_facts` — structured-output helpers using `instructor`-style JSON schema mode.
- `server/src/server/db.py` — `embed_text(text, dimensions=768)` — wraps `text-embedding-004` with retry + caching.
- `server/src/server/embedding_cache.py` — Postgres-persistent L2 cache for `embed_text` (we paid the price once, cached the result).
- `server/src/server/gemini_budget.py` — process-wide cooldown + per-minute rate-limit guard. Critical when 50/min limits would otherwise tank a long ingest run.
- `server/src/server/ontology/propose.py:223` — `infer_source_mapping` — sends sample payloads + the `MappingProposal` schema to gemini-2.5-flash, parses back to a Pydantic model.
- `server/src/server/cli.py` — `cmd_infer_source_mappings` — CLI driver around the above.

Entry point at config: `server/src/server/config.py` reads `GEMINI_API_KEY` + `GEMINI_MODEL`.

## Architectural decisions involving Gemini

- **Why Gemini for embeddings instead of OpenAI?** Single-vendor consolidation. We use Gemini for everything LLM-shaped, and `text-embedding-004` is competitive with `text-embedding-3-small`. One key, one rate-limit budget, one billing line.
- **Why Pioneer Tier 3.5 *before* Gemini for entity disambiguation?** Pioneer is a fine-tuned NER (smaller, faster, deterministic). Gemini is the fallback when Pioneer is unavailable — see `_llm_free_text_facts` in `engine.py`.
- **Why structured output via `response_schema` for mapping inference?** Mapping configs are gnarly JSONata expressions inside a typed schema. Free-form completions hallucinate paths that don't exist. With `response_schema` + post-validation (`validate_proposal`) we catch ~90% of bad mappings before they ever land in `source_type_mapping`.

## Honesty notes

- Pioneer-fallback path was added late — for source-types where Pioneer returns nothing, `extract_email_facts` (Gemini structured-output) takes over. Both paths emit the same `PendingFact` shape so downstream resolver doesn't care.
- The autonomous-ontology path produces "pending" mappings when Gemini's confidence ≤ 0.95 OR when the mapping introduces new entity/edge types. We deliberately routed those to a human-review inbox rather than blind-auto-approve. See `should_auto_approve` in `propose.py`.

## Demo snippet

```bash
# Trigger mapping inference for a brand-new source_type
uv run server infer-source-mappings --only my_new_type

# Backfill embeddings for entities that don't have one yet
uv run server backfill-embeddings --limit 50

# Check Gemini call/cap/cooldown stats from the running process
uv run server gemini-stats
```

## What we'd do with more time

- Use gemini-2.5-pro multimodal at *resolve* time on invoice PDFs (currently the connector is "dumb" — text only — to avoid a previous 17-min hang).
- Cache mapping-inference results across teams so the second team to ingest "email" gets the existing mapping for free.
- Promote `gemini_budget` from process-local to Redis-backed so multi-worker deployments share one rate-limit budget.
