> **Internal team prep doc.** This was the kickoff document used by the team during the 48h hackathon. The jury-facing submission lives in [`/README.md`](../README.md). Kept for archival reasons.

# Big Hack Berlin — Qontext Track (team prep)

**Event:** Tech Europe Hack, Berlin
**Start:** 2026-04-25 · **Submission deadline:** Sunday 14:00
**Track:** [Qontext](https://qontext.ai/?utm_source=luma) — turn fragmented company data into a context base AI can operate on
**Repo:** https://github.com/lassejohannis/TechEurope

---

## 1. Challenge

Most AI systems reconstruct company reality at runtime by pulling scattered facts from mail, CRM, policies, tickets, docs, and chat — hoping the prompt is good enough. Qontext argues this doesn't scale.

**Input:** simulated enterprise dataset — email, CRM, HR, policy documents, collaboration/workspace data, IT service data, business records (provided on event day).

**Output:** a virtual file system + graph that documents the business and is legible to both machines and humans.

### Goal

Build a system that turns the dataset into a structured company memory:

- **Virtual file system** that documents the business:
  - static data (employees, customers, products)
  - procedural knowledge (processes, SOPs, rules)
  - trajectory information (tasks, projects, progress)
- **Explicit references** — links between files, and links to the underlying source records.
- **Interface(s)** for AI systems to retrieve context efficiently, and for business users + AI to inspect, validate, edit, and extend the company memory.

### Criteria for a strong solution

- Generalize beyond the provided dataset and data format.
- Resolve easy information conflicts automatically; involve humans where ambiguity actually matters.
- Preserve **provenance at the fact level** and update automatically when source facts change.

### Anti-patterns

- Dumping markdown into folders.
- Building a documentation chatbot.

The brief emphasizes: explainable, editable, robust under change, useful in practice. Cover both **graph construction** and **retrieval**. Treat the VFS as a **product surface**, not just storage.

Detail: [docs/qontext-case.md](docs/qontext-case.md)

---

## 2. Submission Requirements

- **Deadline:** Sunday 14:00
- **Team:** max. 5 people
- **Partner tech:** min. **3 partner technologies** (Aikido excluded from the 3)
- **Newly built** at the hackathon (boilerplates allowed)

### What to submit

- **2-minute video demo** (Loom or equivalent) — live walkthrough of key features.
- **Public GitHub repo** — README with setup + install instructions, clear documentation of all APIs/frameworks/tools, enough technical docs for the jury.

### Competition format — two stages

1. **Pre-Selection** — 8 finalist teams (1 per track) advance. Judging: creativity, technical complexity, bonus for effective use of partner tech.
2. **Finalist Stage** — 5-min live pitch to jury + audience. Jury picks top 3 winners.

Detail: [docs/hack-rules.md](docs/hack-rules.md)

---

## 3. Technology Partners

Rule recap: min. 3 required. **Aikido is NOT eligible as one of the 3.**

| Partner | What it is | Onboarding / docs |
|---|---|---|
| [Google DeepMind](https://deepmind.google/) | Frontier multimodal models (Gemini). Temporary accounts issued on site. | [How to use the temp account](https://goo.gle/hackathon-account) |
| [Tavily](https://www.tavily.com/) | Real-time search, extraction, research, web crawling API. | [docs.tavily.com](https://docs.tavily.com/welcome) — 1000 free credits on signup; top-up code in `NOTES.local.md` |
| [Lovable](https://lovable.dev) | AI-chat app/website builder. | Pro-Plan-1 discount code in `NOTES.local.md` — Settings → Plans & Credits → monthly plan → checkout |
| [Gradium](https://gradium.ai/) | Voice AI models for realtime interactions. | [api_docs](https://gradium.ai/api_docs.html) — after signup, ping Pratim on site or Discord `#gradium` with your org name |
| [Entire](https://entire.io/?utm_source=luma) | Developer platform for agent-human collaboration. | [CLI installation](https://docs.entire.io/cli/installation) |
| [Aikido](https://www.aikido.dev/) — ***not eligible as 1 of 3*** | Security scanning. Free Pro trial during the event. | [app.aikido.dev/login](https://app.aikido.dev/login) |
| [Pioneer](https://pioneer.ai/) by [Fastino](https://fastino.ai/) | "Models that train themselves." Synthetic data gen + eval + adaptive inference. | Onboarding page in the hack's Notion |

Fit analysis + Path-A vs Path-B partner combo decision: [docs/stack.md](docs/stack.md).

---

## 4. Side Challenges

Stackable on top of the Qontext track prize.

| Challenge | Requirement | Prize |
|---|---|---|
| **Fastino — Best use of Pioneer** | Use Pioneer. Fine-tune a model that outperforms / replaces a general-purpose LLM API call. Thoughtful use of synthetic data, evals, adaptive inference. Bonus for creative GLiNER2. | **700€** (Mac Mini cash value) |
| **Aikido — Most Secure Build** | Create account, connect Git, connect repo, screenshot security report. | **1000€** |
| **Gradium — Best use of Gradium** | Use Gradium. Confirm in submission. | 900k Gradium credits + goodies |
| **Entire — Best use of Entire** | Use Entire. Confirm in submission. | $1000 Apple gift cards + Switch 2 + PS5 + Xbox |

Detail: [docs/side-challenges.md](docs/side-challenges.md)

---

## 5. Product Direction

We build **two layers + a demo surprise** — direct alignment with Qontext's stated direction (*"use-case agnostic context layer at the core + revenue intelligence use case on top"*).

1. **Core Context Infrastructure** — horizontal, use-case-agnostic. Ingestion, entity resolution, graph, VFS, provenance, change streams. The thing every AI app should plug into.
2. **Revenue Intelligence App** — vertical proof-of-value sitting on top of the Core. Morning Action Feed with prepared drafts. Validates the platform with a real ROI story.
3. **Second App (live demo surprise)** — minimal HR or Finance view on the same Core, started live at pitch end. Proves horizontality.

**Hard rule:** Core code must contain zero Revenue terminology. The Revenue App consumes only the Core's public Query API.

Detail: [docs/team-briefing-technical.md](docs/team-briefing-technical.md) (engineering) and [docs/team-briefing-commercial.md](docs/team-briefing-commercial.md) (business + pitch).

## 6. Stack (locked + open)

### Locked
| Layer | Choice |
|---|---|
| Frontend | Vite + React + TypeScript + Tailwind + shadcn/ui |
| Graph viz | react-flow |
| Backend | FastAPI (Python 3.12) + uv |
| **Database (everything)** | **Supabase (Postgres + pgvector + Realtime + Auth + Storage)** |
| Graph store | Postgres `nodes` + `edges` tables, recursive CTEs |
| Vector store | pgvector (column on `entities` and `facts`) |
| LLM | **Gemini (Google DeepMind)** — partner-eligible |
| MCP server | `modelcontextprotocol` Python SDK |
| Connectors | Mock-from-JSON in `data/raw/` |

### Open — partner combo (decide Day 1)

Two viable paths, both stack with Aikido for the security side prize:

**Option A — Technical heavyweight:** Gemini + Pioneer (fine-tuned GLiNER2) + Entire (HITL)
**Option B — Ecosystem play:** Gemini + Tavily (research) + Gradium (call STT)

Detail + decision criteria: [docs/stack.md](docs/stack.md)

**Total achievable prize stack:** Qontext track (1g gold/member + dinner) + Aikido 1000€ + side prizes from whichever partners we pick + Stage-2 finalist prizes.

---

## 7. Design docs

**Read in order — most important first:**

| # | Doc | What's in it |
|---|---|---|
| 1 | [docs/qontext-case.md](docs/qontext-case.md) | The sponsor brief verbatim |
| 2 | [docs/team-briefing-technical.md](docs/team-briefing-technical.md) | Engineering plan: two-layer architecture, Core Layer principles, demo flow (canonical) |
| 3 | [docs/team-briefing-commercial.md](docs/team-briefing-commercial.md) | Business + pitch: ICP, GTM, validation (Luca/Hypatos), pitch story |
| 4 | [docs/stack.md](docs/stack.md) | Stack decisions (locked) + open partner-combo question |
| 5 | [docs/data-model.md](docs/data-model.md) | `SourceRecord` / `Entity` / `Fact` / `Resolution` schemas |
| 6 | [docs/mcp-tools.md](docs/mcp-tools.md) | 5 agent-facing MCP tools with full I/O specs |

**Background / operational:**

| Doc | Purpose |
|---|---|
| [docs/team-brainstorm.md](docs/team-brainstorm.md) | Pain points, ICP, ideas A–E, market analysis — why we landed here |
| [docs/team-setup.md](docs/team-setup.md) | Pre-hack checklist, MCP auth steps, kickoff agenda, risk register |
| [docs/skills.md](docs/skills.md) | Claude Skills shipped with the repo and how to add more |
| [docs/hack-rules.md](docs/hack-rules.md) | Submission rules + competition format |
| [docs/side-challenges.md](docs/side-challenges.md) | Side prizes + stacking strategy |

## 8. Prize overview

- **Qontext track prize:** 1g real gold bar per team member + private dinner with Qontext
- **Side prizes:** see section 4
- **Stage-2 finalist prizes:** announced separately (top 3 after the live pitch)

---

## Project layout

```
.
├── README.md                          ← this file (single source of truth)
├── NOTES.local.md                     ← gitignored; partner codes
├── .mcp.json                          ← project-scoped MCP servers (Supabase configured)
├── .claude/skills/                    ← Claude Skills auto-loaded for the team
│   ├── supabase/                        Supabase domain expertise + security checklist
│   ├── supabase-postgres-best-practices/  Indexing, RLS, locks, monitoring
│   ├── shadcn/                          Component composition, styling, forms, icons
│   ├── vercel-react-best-practices/     40+ React/Next.js performance rules
│   └── web-design-guidelines/           100+ UI / a11y / UX review rules
├── .agents/skills/                    ← same skills, mirrored for non-Claude tools
├── docs/
│   ├── qontext-case.md                  case brief (sponsor)
│   ├── hack-rules.md                    submission rules
│   ├── side-challenges.md               side prizes + stacking strategy
│   ├── team-briefing-technical.md       two-layer architecture, demo flow (canonical)
│   ├── team-briefing-commercial.md      ICP, GTM, validation, pitch story
│   ├── team-brainstorm.md               pain points, ideas A–E, market analysis
│   ├── stack.md                         stack decisions (locked + open)
│   ├── data-model.md                    shared schemas
│   ├── mcp-tools.md                     agent-facing API spec
│   ├── team-setup.md                    pre-hack checklist + MCP auth + kickoff
│   └── skills.md                        skill library (what's installed, how to add)
└── .gitignore
```

**Status:** boilerplate is in place (Vite + React + TS + Tailwind + shadcn/ui + TanStack Query frontend; FastAPI + uv backend; Vite-proxied dev). Day-1 work fills in the Core Context Engine + Revenue Intelligence App on top of this scaffold.

---

## Quickstart

Prerequisites: Node 20+, Python 3.12+, `uv`, `npm`.

```bash
# Clone
git clone https://github.com/lassejohannis/TechEurope.git
cd TechEurope

# Install everything
make install

# Set env vars (copy templates, fill in values)
cp web/.env.example web/.env
cp server/.env.example server/.env

# Run web (5173) + server (8000) together
make dev
```

Open http://localhost:5173 — you should see "Boilerplate live." and a **Re-ping** button hitting `/api/hello` through the Vite proxy.

Run them separately if you prefer:
```bash
make web      # Vite dev server, port 5173
make server   # FastAPI dev server, port 8000
make build    # Production build of the frontend
```

### Project layout (top level)

```
.
├── web/        Vite + React + TS frontend (Tailwind v4 + shadcn/ui + TanStack Query + react-flow + zustand)
├── server/    FastAPI backend (uv-managed; supabase + google-genai + mcp on the deps list)
├── Makefile   `make install / dev / web / server / build / clean`
├── docs/      Design docs (read order in section 7)
├── .mcp.json  Project-scoped MCP servers (Supabase + shadcn)
└── .claude/skills/  Project-scoped Claude Skills (5 installed)
```
