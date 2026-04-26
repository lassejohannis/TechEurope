# Partner Technologies — Deep Dives

Each partner has a dedicated README documenting how their technology is used in this project: code paths, architectural decisions, demo snippets, and honest notes on what's live vs. roadmap. These pages are written for **the partners themselves** — you should be able to evaluate our use of your tech without reading the rest of the repo.

## Partners in this project

| Partner | Role in the project | Code Footprint | Status | Deep-dive |
|---|---|---|---|---|
| **Gemini** (Google DeepMind) | Embeddings · autonomous mapping inference · structured extraction | 130+ refs across 8 files | live | [`gemini/`](./gemini/) |
| **Pioneer** (Fastino) | Tier-3.5 of the resolution cascade · free-text fact mining | `extractors/pioneer.py` + cascade hook + post-filter | live | [`pioneer/`](./pioneer/) |
| **Tavily** | Public-web entity enrichment connector | `connectors/tavily.py` | live (CLI-driven) | [`tavily/`](./tavily/) |
| **Aikido** | SCA · SAST · secrets · IaC scanning | `.aikido/` config | configured | [`aikido/`](./aikido/) |
| **Entire** | Multi-agent code review · session/decision history · checkpoint recovery | dev tool, no product code | used throughout | [`entire/`](./entire/) |

## Cross-cutting integration story

Two partners get called *inside* the resolution pipeline:

1. **Gemini** runs at three distinct stages: `text-embedding-004` for `entities.embedding` (Tier-3 kNN), `gemini-2.5-flash` for autonomous mapping inference (Gemini designs JSONata configs from sample payloads), `gemini-2.5-pro` for PDF multimodal extraction.
2. **Pioneer** is Tier-3.5 of the entity-resolution cascade — fires when `0.86 ≤ embedding similarity < 0.92`, the disambiguation zone where Gemini-only would either hallucinate or punt to inbox.

**Tavily** runs out-of-band as an enrichment connector (`uv run server enrich-entity <id>`) — pulls public web context for entities flagged with low source diversity.

**Aikido** sits in CI (configured but not gating).

**Entire** is the dev loop our engineering team used: session-history search, multi-agent code review (`/ultrareview`), checkpoint-recovery during the sprint.

See each partner's deep-dive for code paths and a self-assessment against their evaluation criteria.
