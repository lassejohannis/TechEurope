# Stack

Pre-hack working choice. Most of it is locked; partner combo + a few details are open for the Day-1 kickoff.

See [team-briefing-technical.md](team-briefing-technical.md) for the canonical engineering plan and [team-briefing-commercial.md](team-briefing-commercial.md) for the business context that shaped these choices.

## Locked decisions

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend framework** | Vite + React + TypeScript | Same output shape as Lovable → friction-free import of generated components. Faster HMR, simpler deploy than Next.js. SSR/RSC not needed for an SPA over our own API. |
| **UI kit** | Tailwind + shadcn/ui + lucide-react | Industry default, max Claude Code fluency, Lovable-native. |
| **Graph viz** | react-flow | Best-in-class for our Graph-Explorer. Handles node/edge rendering + pan/zoom + custom node components. |
| **Data fetching (frontend)** | @tanstack/react-query + supabase-js | Server-state caching + Realtime subscriptions out of the box. |
| **Client state** | zustand | Minimal boilerplate. |
| **Markdown rendering** | react-markdown + rehype | VFS file viewer with custom citation components. |
| **Backend framework** | FastAPI (Python 3.12+) | Fast, async, auto OpenAPI, tight Pydantic integration. |
| **Python deps mgmt** | uv | Fast installs, lockfile, workspace-aware. |
| **Database (everything)** | **Supabase (Postgres 15 + pgvector + Realtime + Auth + Storage)** | One service for SQL + vectors + change streams + auth + raw artifacts. Local dev via `supabase start` (Docker-backed CLI). Replaces Qdrant + NetworkX + SQLite + custom auth in a single move. |
| **Graph store** | **Postgres** (`nodes` + `edges` tables; recursive CTEs for traversal) | Team brief explicitly listed this as the acceptable fallback to Neo4j. We dropped Neo4j: viz comes from `react-flow` in the frontend, not from Neo4j Browser. |
| **Vector store** | **pgvector** (Supabase column on `entities` and `facts`) | Same DB as everything else. Filter by status/confidence works natively. |
| **LLM provider** | **Gemini (Google DeepMind)** | Partner-eligible. Multimodal handles policy PDFs with images. Long context for draft generation. Claude is not on the partner list, so we don't use it. |
| **Embeddings** | Gemini `text-embedding-004` (or current equivalent) | Same partner stack, multilingual. |
| **MCP server** | `modelcontextprotocol` Python SDK | 5–6 tool surface for AI agents (see [mcp-tools.md](mcp-tools.md)). |
| **REST Query API** | FastAPI endpoints | For the Revenue App and other web clients. Same business logic as MCP, different transport. |
| **Change streams** | Supabase Realtime | Tables `facts` / `entities` have replication enabled. Frontend subscribes via `supabase.channel(...)`. No custom WebSocket server. |
| **Auth (Revenue App)** | Supabase Auth | Email/password or magic link for the demo login. Trivial to wire. |
| **Connectors** | Mock-from-JSON files in `data/raw/` | Team decision. No live API integrations during the hack — sample dataset will be file-based anyway. |
| **Security scan** | Aikido | Connect repo Day 1 → screenshot at submission for the 1000€ side prize. |
| **Repo layout** | Two folders (`web/`, `server/`) — no workspace tooling | Overhead not worth it for 30h + small team. |

## Partner combo — RESOLVED (2026-04-25)

**Decision:** Pioneer + Gemini + Entire (Dev-Tool) + Aikido. Vollständige Spec in [`partner-tech.md`](partner-tech.md).

| Partner | Rolle | Side-Prize |
|---|---|---|
| **Google DeepMind (Gemini)** | Im Produkt: Embeddings, Reasoning, Multimodal | — |
| **Pioneer (Fastino)** | Im Produkt: Fine-tuned GLiNER2 für E+R-Extraction am Hot-Path (Cascade Tier 3.5) | 700€ |
| **Entire** | Dev-Tool: Coding-Provenance + Checkpoints (nicht im Produkt) | $1000 |
| **Aikido** | Security-Scan auf Repo | 1000€ |

**Story:** "Hand-rolled deterministic-first ER cascade. Pioneer-finetuned GLiNER2 schlägt Gemini am Hot-Path bei Cost/Latency. Gemini powered alles andere. Entire gibt uns Coding-Provenance, Aikido sichert das Repo."

**Side-prize stack:** ~2700€ + $1000 goodies on top of Qontext track prize.

**Day-1-Validation:** Mit Orga klären ob Entire als Dev-Tool für Pflicht-3 zählt. Falls nein → Tavily als 3. Produkt-Partner einbauen (~3h, Adapter-Pattern wie Email/CRM-Mock).

**Verworfene Alternativen:**
- *Path B* (Gemini + Tavily + Gradium) — geringere technische Tiefe, Gradium-STT-Risiko
- *Splink* als ER-Matcher — 6-10h Time-to-Value vs 4h hand-rolled (siehe Cowork-Research)
- *Lovable* als 3. Pflicht-Partner — passive Stack-Kompatibilität, kein bewusster Use-Case

## Open: Revenue App details

Decide Day 1 with the team:

- Which 5–7 patterns power the Morning Action Feed? Candidates: silent deal (no activity in N days), champion at risk (champion left thread/company), budget signal (CFO joined thread), technical blocker (security/eng objection surfaced), expansion signal (positive feedback + usage uptick), competitive mention (competitor named in comm), churn warning (escalating tickets, exec calls stopped).
- Which 1–2 deals get the deep "Deal Evidence View"?
- Which 3 action types get prepared drafts?
- HR-Onboarding or Finance-Briefing as the Second App?

## Excluded on purpose

- **Next.js** — SSR/RSC add complexity we don't need; Vite is faster for hack.
- **Neo4j** — Postgres + recursive CTEs covers our graph queries; viz lives in `react-flow`.
- **Qdrant** — pgvector in Supabase covers the same filtering needs without an extra service.
- **SQLite** — Supabase Postgres is the source of truth.
- **Claude Anthropic API** — not on the partner list; Gemini covers LLM needs and counts as Google DeepMind partner usage.

## Non-decisions (don't relitigate Day 1)

To protect build time:

- Framework religion — Vite is chosen, move on.
- Styling system — Tailwind + shadcn, move on.
- Backend language — Python, move on.
- Whether to use a vector DB — yes, pgvector via Supabase, move on.
- Whether to use an auth provider — yes, Supabase Auth, move on.
