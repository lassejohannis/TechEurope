# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Big Berlin Hack 2026, **Qontext track**. We are building a two-layer product:

1. **Core Context Engine** (horizontal, use-case agnostic) — ingestion → entity resolution → graph + VFS + temporal facts + provenance, exposed via REST + 5 MCP tools.
2. **Revenue Intelligence App** (vertical, on top) — consumes only the Core's public Query API.
3. **Second app (HR/Finance)** started live at the pitch end to prove horizontality.

Authoritative design docs (read in this order):
- `docs/qontext-case.md` — sponsor brief
- `docs/team-briefing-technical.md` — canonical engineering plan, schemas, demo flow, scope cuts
- `docs/stack.md` — locked stack + open partner-combo decision
- `docs/data-model.md` — `SourceRecord` / `Entity` / `Fact` / `Resolution`
- `docs/mcp-tools.md` — agent-facing API spec (5 tools)
- `docs/partner-tech.md` — Pioneer / Gemini / Entire / Aikido allocation
- `docs/workstreams.md`, `docs/team-setup.md` — kickoff, ownership, risks

## Hard architectural rules

These are review criteria, not suggestions:

- **No Revenue terminology in Core code.** Core knows `Person`/`Company`/`Communication`, not "Opportunity"/"Champion"/"Stage". Litmus test: building HR/Finance on top must require zero Core changes.
- **Revenue App talks only to the Query API**, never the DB directly.
- **Attribution is non-optional.** Every Fact has `derived_from` (NOT NULL); every API response carries `{value, confidence, evidence: [...]}`.
- **Postgres is source of truth.** Neo4j is a read-only projection synced via Supabase Realtime — never dual-write.
- **Entity- and edge-types live in YAML ontologies** (`config/ontologies/*.yaml`) loaded into `entity_type_config` / `edge_type_config` tables. Adding a domain = new YAML, no code change.
- **Bi-temporal facts:** `tstzrange` + `EXCLUDE USING GIST` + supersede trigger. Always `tstzrange`, never `tsrange`. Re-derivation is **lazy** (`needs_refresh` flag), no cron.
- **Resolution cascade is hand-rolled and deterministic-first** (hard ID → alias → embedding kNN → Pioneer GLiNER2 → context heuristics → ambiguity inbox). Do not pull in Splink/Zingg/Cognee/Graphiti at runtime — steal patterns, don't import. See "Adopted OSS" section of `team-briefing-technical.md`.
- **Idempotent ingest:** `content_hash` + deterministic IDs (`{source_type}:sha256:{hash}`). Re-ingest = update.

## Repository layout

```
web/        Vite + React 19 + TS + Tailwind v4 + shadcn/ui + TanStack Query + react-flow + zustand
server/     FastAPI (Python 3.12, uv-managed). Entry: server.cli:main → server.main:app
  src/server/sync/neo4j_projection.py   Realtime → idempotent Cypher MERGE worker (skeleton)
data/enterprise-bench/                  Provided dataset (mail, CRM, HR, ITSM, policy, workspace, tasks.jsonl)
docs/                                   Design docs (single source of truth)
.mcp.json                               Project-scoped MCP servers (Supabase HTTP + shadcn stdio)
.claude/skills/                         Project-scoped Claude Skills (supabase, postgres, shadcn, react, web-design)
.agents/skills/                         Same skills mirrored for non-Claude tools
NOTES.local.md                          Gitignored — partner discount/top-up codes
```

## Common commands

```bash
make install           # web: npm install · server: uv sync
make dev               # Vite (5173) + FastAPI (8000) concurrently. /api proxied by Vite.
make web               # frontend only
make server            # backend only (uv run server, with --reload)
make build             # tsc -b && vite build
make clean             # nuke dist, node_modules/.vite, .venv, caches

# Web
cd web && npm run dev | npm run build | npm run lint | npm run preview

# Server
cd server && uv sync
cd server && uv run server                 # dev server
cd server && uv run ruff check .           # lint
cd server && uv run ruff format .          # format
cd server && uv run pytest                 # all tests
cd server && uv run pytest path/to/test_x.py::test_name   # single test
```

Sanity check: open http://localhost:5173 — boilerplate pings `/api/hello` through the Vite proxy to FastAPI on 8000.

## Stack (locked)

- Frontend: Vite + React 19 + TS + Tailwind v4 + shadcn/ui + TanStack Query + react-flow + zustand + react-router 7.
- Backend: FastAPI + Pydantic v2 + pydantic-settings, `uv` for deps, ruff for lint/format, pytest (+ pytest-asyncio).
- DB / everything: **Supabase** (Postgres + pgvector HNSW + Realtime + Auth + Storage). Graph store = Postgres `nodes`/`edges`/`facts` with recursive CTEs; Neo4j Aura is an optional read-only projection (hard-cap Saturday 14:00 — drop to Postgres-only otherwise).
- LLM: **Gemini** (`text-embedding-004` for embeddings, `gemini-2.0-flash` for ambiguity resolution, `gemini-2.5-pro` for drafts/PDF). Use `instructor` for structured outputs.
- MCP: Python `mcp` SDK exposes the 5 agent-facing tools (see `docs/mcp-tools.md`).

`server/.env` config keys (see `server/src/server/config.py`): `API_HOST`, `API_PORT`, `API_CORS_ORIGINS`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `GEMINI_API_KEY`, `GEMINI_MODEL`.

## Tooling notes

- Project-scoped MCP servers are declared in `.mcp.json` (Supabase HTTP, shadcn stdio). The Supabase MCP is wired to the project ref already; prefer it for DB-shape questions over guessing.
- Claude Skills shipped under `.claude/skills/` (supabase, supabase-postgres-best-practices, shadcn, vercel-react-best-practices, web-design-guidelines) auto-load — defer to them for domain best practices.
- `NOTES.local.md` holds partner credentials (Tavily top-up, Lovable discount, etc.) — gitignored, never commit. `.env` likewise.

## Submission constraints

- Deadline **Sunday 14:00**. Min. **3 partner technologies** in the submission (Aikido does not count toward the 3).
- 2-min Loom + public GitHub repo with setup docs.
- Code must be newly built at the hackathon (this boilerplate is allowed).

## Scope discipline

If something is not in the priority list in `docs/team-briefing-technical.md` § "Build-Priorisierung für 48h", it is cut. The Revenue App is intentionally trimmed (3 patterns, 1 deal view, 2 action types) to protect Core completeness and the human-facing UI.
