# Tavily

**Pflicht-Partner**: counts toward the required-3.
**Side-Prize**: via sponsor relationship (no public side-prize amount listed).

## What we use it for

Tavily is our **entity-enrichment** layer. The Core engine ingests private enterprise data — but real-world entities (customers, vendors, regulators) often need *public* context to be useful: HQ city, industry classification, founding year, recent news.

We expose Tavily as a connector that enriches existing entities on demand, not a bulk-ingest source.

## How it's wired in

```
              entity flagged with low source_diversity
                            ↓
            uv run server enrich-entity <entity_id>
                            ↓
            TavilySearchConnector.search(canonical_name + type-hint)
                            ↓
                     Tavily REST API
                            ↓
            web_search source_records (idempotent via content_hash)
                            ↓
                  resolve --source-type web_search
                            ↓
            Pioneer/Gemini extract additional facts
                            ↓
              entity gains new facts with web provenance
```

The enrichment trigger is **operator-driven** — there's no auto-fire on every entity (would burn quota). The CLI command supports a target entity ID, and the connector emits `web_search` source records that flow through the standard resolve pipeline.

## Code paths

- `server/src/server/connectors/tavily.py` — `TavilySearchConnector(BaseConnector)` with `source_type = "web_search"`. Implements `discover()` (Tavily API call) and `normalize()` (search hit → SourceRecord).
- `server/src/server/connectors/__init__.py:69-73` — registers the connector eagerly so `uv run server ingest --connector web_search ...` is wired.
- `server/.env` — `TAVILY_API_KEY` (free 1k queries/month tier).
- Demo seed file: `server/data/seed_web_search_demo.json` (so the demo doesn't depend on live Tavily availability).

## Architectural decisions involving Tavily

- **Why on-demand vs auto-enrich every entity?** Quota economics. 1k queries/month means we can't fire on every newly-resolved entity. The fastest signal that an entity needs enrichment is `entity_trust.source_diversity == 1` — only one private source has touched it. The CLI lets a human or a webhook target those.
- **Why a connector vs an ad-hoc script?** Reuse. By making web-search a `BaseConnector`, the resulting records flow through the same idempotency rails (`content_hash`), the same mapping engine (Tavily-results need a JSONata mapping like any other source), and the same resolver — Pioneer extracts org/person/location facts from the snippet text just like it does from email bodies.
- **Why `--seed` fallback?** Hackathon demos need to be deterministic. With `--seed data/seed_web_search_demo.json` the demo runs without internet — useful when the venue WiFi dies.

## Side-Prize criteria (self-assessed)

| Kriterium | Status | Evidence |
|---|---|---|
| Real production use | ✅ | Connector lives at `connectors/tavily.py`, registered, callable |
| Quota-aware design | ✅ | On-demand only; not hooked into auto-fire pipelines |
| Graceful offline mode | ✅ | `--seed` flag bypasses Tavily for demos |
| Output flows through normal cascade | ✅ | Web hits become `web_search` source_records → standard resolve pipeline |

## Demo snippet

```bash
# Enrich a specific entity with public web context
uv run server enrich-entity organization:inazuma-com

# Or run the offline demo
uv run server ingest --connector web_search \
  --seed data/seed_web_search_demo.json
uv run server resolve --source-type web_search --limit 10
```

Expected effect: `entity_trust.source_diversity` for `organization:inazuma-com` increases from 1 → 2+, the entity gains facts like `headquartered_in`, `industry`, `founded`.

## What we'd do with more time

- Auto-detect enrichment candidates (`source_diversity == 1` AND `fact_count < 3`) and queue them for nightly enrichment.
- Cache Tavily results in `embedding_cache` to dedup repeated lookups.
- Add a "freshness" tier: re-enrich high-trust entities every 30 days for news/changes.
