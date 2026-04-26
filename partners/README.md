# Partner Technologies — Deep Dives

Each partner gets a dedicated README with use-case, code paths, side-prize criteria, and a 30-second demo snippet. These are designed for the **side-prize juries** (separate from the main jury) — they should be able to evaluate our use of their tech without reading the main repo.

| Partner | Side-Prize | Pflicht-Partner? | Code Footprint | Status | Detail |
|---|---|---|---|---|---|
| **Gemini** (Google DeepMind) | — | ✅ counts toward 3 | 130+ refs across 8 files | live | [`gemini/`](./gemini/) |
| **Pioneer** (Fastino) | 700 € | ✅ counts toward 3 | `extractors/pioneer.py` + cascade hook + filter | live | [`pioneer/`](./pioneer/) |
| **Tavily** | sponsor relation | ✅ counts toward 3 | `connectors/tavily.py` | live (CLI-driven) | [`tavily/`](./tavily/) |
| **Aikido** | 1 000 € | ❌ excluded from 3 | `.aikido/` config | evaluated | [`aikido/`](./aikido/) |
| **Entire** | $ 1 000 | ❌ excluded from 3 | dev-tool, no product code | used throughout | [`entire/`](./entire/) |

## Compliance with hackathon rules

- **Required**: at least 3 partner technologies (Aikido excluded).
- **Our 3**: Gemini · Pioneer · Tavily — all three live in production-path code, not just `requirements.txt` entries.

## Cross-cutting integration story

Two partners get called *inside* the resolution pipeline:

1. **Gemini** runs at three distinct stages: text-embedding-004 for `entities.embedding` (Tier-3 kNN), gemini-2.5-flash for autonomous mapping inference (Gemini designs JSONata configs from sample payloads), gemini-2.5-pro for PDF multimodal extraction.
2. **Pioneer** is Tier-3.5 of the entity-resolution cascade — fires when `0.86 ≤ embedding similarity < 0.92`, the disambiguation zone where Gemini-only would either hallucinate or punt to inbox.

**Tavily** runs out-of-band as an enrichment connector (`uv run server enrich-entity <id>`) — pulls public web context for entities flagged with low source diversity.

**Aikido** sits in CI (configured but not gating).

**Entire** is the dev-loop our engineering team used: session-history search, multi-agent code review (`/ultrareview`), checkpoint-recovery during the 48h sprint.

See each partner's deep-dive for code paths and side-prize criteria self-assessment.
