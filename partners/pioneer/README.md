# Pioneer (Fastino — GLiNER2)

**Side-Prize**: 700 €.
**Pflicht-Partner**: counts toward the required-3.

## What we use it for

Pioneer is a fine-tuned GLiNER2 model — a small, fast NER + relation-extraction model that fills the gap between deterministic-string-matching and full-LLM reasoning. We slot it into our resolution cascade as **Tier 3.5**, the disambiguation zone.

Two distinct integration points:

1. **Free-text fact mining** — extracts entities + relations from long string payloads (`email.body`, policy-PDF `text`, chat threads). Runs *inside* the resolve step, before facts are persisted.
2. **Tier-3.5 entity disambiguation** *(roadmap stub — interface present, behavior pending)* — kicks in when pgvector kNN scores fall in the 0.86–0.92 ambiguity band. Hook is `extract_and_match` in `extractors/pioneer.py:309`.

## How it's wired in

```
SourceRecord.payload
        ↓
apply_mapping (JSONata structured extraction)
        ↓
  ┌─────┴─────┐
  ↓           ↓
JSON-derived  free-text path (e.g. $.body, $.text)
candidates    longer than 200 chars
              ↓
       pioneer.extract(text, source_type=...)
              ↓
       ExtractionResult
       ├── entities: [(type, slug)]
       └── facts:    [(subject_id, predicate, object_id, confidence)]
              ↓
       _llm_free_text_facts (engine.py:381)
              ↓
       Pseudo-entity post-filter (engine.py:_is_pseudo_entity)
              ↓
       PendingFact[] → cascade tiers 1-5
```

The post-filter is the second-half of our Pioneer integration: GLiNER2 sometimes labels common nouns (`"Inazuma.co employees"`, `"Hardware Assets"`, `"Legal &amp"`) as `person`. We block those at materialization time (see `_is_pseudo_entity`) and supplement with a per-source-type **label whitelist** (`_SOURCE_TYPE_LABEL_WHITELIST` in `pioneer.py`) so policy-PDF scans never even ask Pioneer for `person`.

## Code paths

- `server/src/server/extractors/pioneer.py:112` — `extract(text, source_type)` — POSTs to `api.pioneer.ai/v1/chat/completions` with `X-API-Key`. Schema: `{entities: [labels], relations: [predicates]}`.
- `server/src/server/extractors/pioneer.py:54-94` — `_approved_entity_types()` / `_approved_edge_types()` — pulls the live ontology so Pioneer's label space tracks the autonomous-ontology layer.
- `server/src/server/extractors/pioneer.py:18` — `_SOURCE_TYPE_LABEL_WHITELIST` — per-source label restriction (skip `person` for `doc_policy`, `invoice_pdf`).
- `server/src/server/extractors/pioneer.py:147-306` — `_parse_response` — translates Pioneer's chat-completions envelope back to typed `ExtractionResult`.
- `server/src/server/ontology/engine.py:53-180` — `FORBIDDEN_ENTITY_TYPES`, `_BAD_NAME_LITERALS`, `_PLURAL_PERSON_SUFFIXES`, `_HTML_ENTITY_RE`, `_COMMON_NOUNS_FOR_PERSON_CHECK`, `_is_pseudo_entity` — the post-filter.
- `server/src/server/ontology/engine.py:351-415` — `_llm_free_text_facts` — Pioneer-first, Gemini-fallback.
- `server/src/server/cli.py:cmd_cleanup_pseudos` — CLI command that backfills the same heuristic over the live DB.
- `server/src/server/resolver/cascade.py:309` — `extract_and_match` Tier-3.5 hook (roadmap stub, deliberately returns `None` today; cascade.py wraps it in try/except).
- `server/tests/test_ws3_pioneer.py:75` — 25 parametrized tests covering real names, observed false-positives, length boundaries, and the multi-word-common-noun pattern.

## Side-Prize criteria (self-assessed)

| Kriterium | Status | Evidence |
|---|---|---|
| Real production use (not just `requirements.txt`) | ✅ | Live in `_llm_free_text_facts` for every source-type with a `≥200`-char text field |
| Demonstrable improvement over LLM-only baseline | ✅ | Search-quality test: post-Pioneer + filter, "Inazuma" top-1 became `document:Inazuma code of ethics` instead of pseudo-`person:"Inazuma.co employees"` |
| Fine-tune story / synthetic data prep | ⚠️ partial | Synthetic-data generation lived in `docs/ws3-pioneer-finetune.md` (planning); model deployed via Pioneer hosted endpoint |
| Failure-mode handling (NER false positives) | ✅ | Per-source label whitelist + 6-rule post-filter (`_is_pseudo_entity`) + cleanup CLI |
| Side-prize-eligible cleanup tooling | ✅ | `uv run server cleanup-pseudo-entities --no-dry-run` is idempotent |

## Honesty notes

- The fine-tune itself was an off-line workstream (WS-3) — by submission time we point at Pioneer's hosted endpoint via `PIONEER_API_KEY`. Synthetic-data prep notebooks are out of scope of this repo.
- Tier-3.5 entity *disambiguation* is a stub today (returns None). Pioneer's free-text *fact* mining is fully wired and runs in production.
- We initially had self-loop bugs (`Total Cost Of Ownership Tco` resolving to itself) and unknown-predicate FK violations from Pioneer-emitted relations. Both are now fixed: self-loop check + auto-register-predicate path in `cli._persist_fact`.

## Demo snippet

```python
from server.extractors import pioneer

text = """
Inazuma.co's Hardware Assets policy applies to all laptops, mobile
phones and other IT-issued devices. The Information Security team
is responsible for compliance audits…
"""

result = pioneer.extract(text, source_type="doc_policy")
for f in result.facts:
    print(f"{f.subject} {f.predicate} {f.object} (conf={f.confidence:.2f})")
```

After our fixes:
- `doc_policy` source-type → label whitelist drops `person` → no more `person:"Inazuma.co employees"`
- `_is_pseudo_entity` blocks `Hardware Assets`, `Information Security Policy`, `Legal &amp` from materialising

## What we'd do with more time

- Wire Tier-3.5 entity disambiguation properly (not just the free-text mining path).
- Compare side-by-side metrics: Pioneer vs Gemini-structured-output on the same 100 records, per source-type.
- Push more domain-specific labels into the whitelist (e.g. `regulation`, `control_objective`) for compliance docs.
