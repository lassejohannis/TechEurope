# Team Setup

Everything a team member does once before / at the start of the hack. Two parts:
1. **Pre-hack checklist** (do tonight) — accounts, tooling, logins.
2. **First session in the repo** — clone, MCP auth, skills auto-load.

Then a **kickoff agenda** for Day 1 + a **risk register** to keep us honest.

---

## 1. Pre-hack checklist

### Accounts to create (before event start)

- [ ] **Aikido** — https://app.aikido.dev/login (Pro trial auto-applied for event participants)
  - After signup: connect Git → connect the `TechEurope` repo
  - Let it scan overnight — Day 2 we only need to screenshot the report (side prize 1000€)
- [ ] **Lovable** — https://lovable.dev
  - Redeem discount code `COMM-BIG-PVDK` (in `NOTES.local.md`) under Settings → Plans & Credits → Pro Plan 1 (monthly)
  - **Must redeem before end of event.** Do it tonight.
- [ ] **Entire** — https://entire.io
  - Install CLI: `brew install --cask entire` (macOS) or see https://docs.entire.io/cli/installation
  - `entire login` once — auth persists globally across all your terminals
  - **Don't run `entire` (init) inside the repo** — Lasse already did. Hooks live in `.claude/settings.json` and the orphan branch `entire/checkpoints/v1` is set up. Cloning + login is enough; tracking is automatic from your first prompt.
- [ ] **Pioneer / Fastino** — https://pioneer.ai (only if Day-1 picks Path A — see [stack.md](stack.md))
  - Read the Big Berlin Hack onboarding page (linked in hack's Notion)
  - Skim GLiNER2 docs
- [ ] **Tavily** — https://tavily.com (only if Day-1 picks Path B)
- [ ] **Gradium** — https://gradium.ai (only if Day-1 picks Path B)
  - Tell Pratim on-site or Discord `#gradium` your org name after signup
- [ ] **Google DeepMind** — temp accounts issued on-site, nothing to prepare

### Local tooling

Verified present on Lasse's Mac (2026-04-24): Node 24.12, npm 11.6, uv 0.10, Python 3.12, git 2.49.

Still to install before Day 1:
- [ ] `pnpm` (optional — npm works): `npm install -g pnpm`
- [ ] Entire CLI (see above)
- [ ] Discord account (event coordination — `#qontext`, `#gradium`, etc.)

### Logins / IDs to have handy on Day 1

- [ ] GitHub: account that has access to https://github.com/lassejohannis/TechEurope
- [ ] Team Discord usernames — collect in `#qontext` channel
- [ ] Phone with WhatsApp — event coordination there

---

## 2. First session in the repo

The repo ships a project-scoped MCP config in [`.mcp.json`](../.mcp.json) and pre-installed Claude Skills under [`.claude/skills/`](../.claude/skills/). Cloning + running Claude Code is enough; **each team member authenticates Supabase MCP individually** in their browser — no shared tokens, no PATs to manage.

### Currently configured MCPs

- **Supabase** — hosted MCP at `https://mcp.supabase.com/mcp`, scoped to project `iaxcvofompnmzxxdymmm`. Read + write (approvals fired by Claude Code per session). Auth: per-user OAuth in browser.
- **shadcn** — stdio server via `npx shadcn@latest mcp`. Tools: browse components, search registries, install via natural language. No auth needed.

### Entire — agent session tracking

Hooks are wired in `.claude/settings.json` (project-scoped). Every Claude Code session in this repo automatically logs to `.entire/` and pushes checkpoints to the orphan branch `entire/checkpoints/v1`. Parallel sessions in multiple terminals all track independently. Useful commands once installed + logged in:

- `entire activity` — dashboard of recent agent work (yours + teammates')
- `entire dispatch` — auto-generate a status report from recent sessions (Slack-/Notion-ready)
- `entire explain <session>` — human-readable summary of one session

Side-prize angle: Entire's "Best use of Entire" challenge ($1000 + Switch 2 + PS5 + Xbox). Just confirm usage in the submission.

### Step 1 — Pull the repo

```bash
git clone https://github.com/lassejohannis/TechEurope.git
cd TechEurope
```

### Step 2 — Open Claude Code

```bash
claude
```

Claude Code detects `.mcp.json` and asks you to approve the new MCP servers (one-time per machine). Accept.

### Step 3 — Authenticate Supabase

In a **regular terminal** (not the IDE-embedded one — the extension intercepts the OAuth redirect), run:

```bash
claude /mcp
```

- Pick the `supabase` server from the list
- Choose **Authenticate**
- Browser opens → log in to Supabase → grant access → done.

Token lives on your machine; nothing is committed.

The **shadcn** server starts itself via `npx` on first use — no auth needed.

> **First-run cold start:** the very first `npx shadcn@latest mcp` downloads the package (5–30s). During this window `claude mcp list` may show `✗ Failed to connect`. Run it again after the download finishes and you'll see `✓ Connected`. The package is cached after that, so subsequent runs are instant.

### Step 4 — Skills auto-load

Five Claude Skills are pre-installed under `.claude/skills/` and auto-activate when their triggers match. No action needed. See [skills.md](skills.md) for what's installed.

### What you can do once auth'd

**Supabase MCP:** list tables / RLS policies, run read queries (always) and write queries (with per-session approval), generate + run migrations, inspect logs / edge functions / storage buckets, read Supabase docs inline.

**shadcn MCP:** browse the full shadcn/ui component catalog, search by name or functionality, install components via natural language (works once the frontend project under `web/` exists with a `components.json`).

### Troubleshooting

- **"MCP server not connected"** — check `claude /mcp` to see status; re-auth if expired.
- **Browser flow fails on macOS** — make sure you're running in a regular terminal, not the IDE-embedded one. The IDE extension intercepts the OAuth redirect.
- **Wrong Supabase project shown** — check `.mcp.json`; the project ref `iaxcvofompnmzxxdymmm` must match the project you have access to.

### Adding more MCP servers later

Use `claude mcp add --scope project ...` to keep new servers committed to the repo (shared with the team). Personal/local-only servers go via `--scope local` instead, which writes to your user-level config and is *not* committed.

Examples we may add during the hack:

- **Aikido** (if they ship an MCP for security findings)
- **Entire** (developer platform — likely has one)
- **Custom MCP server** — our own exposing the Core Layer's `search_memory`, `get_entity`, `get_fact`, `list_recent_changes`, `propose_fact` tools (see [mcp-tools.md](mcp-tools.md))

---

## 3. Pre-read for the team (skim before Day 1)

Reading priority — most important first:

1. [README.md](../README.md) — one-page overview
2. [docs/qontext-case.md](qontext-case.md) — the sponsor brief (the case)
3. [docs/team-briefing-technical.md](team-briefing-technical.md) — what we're building (engineering, canonical)
4. [docs/team-briefing-commercial.md](team-briefing-commercial.md) — what we're pitching (Sunday-relevant)
5. [docs/data-model.md](data-model.md) — schemas we'll implement
6. [docs/mcp-tools.md](mcp-tools.md) — the agent-facing API
7. [docs/stack.md](stack.md) — tech decisions + open partner-combo question

Background (read if time):
- [docs/team-brainstorm.md](team-brainstorm.md) — pain points, ICP, ideas A–E, why we landed here
- [docs/hack-rules.md](hack-rules.md) — submission rules
- [docs/side-challenges.md](side-challenges.md) — side prizes + stacking strategy
- [docs/skills.md](skills.md) — what skills auto-load and how to add more

---

## 4. Kickoff agenda (first 30 min, Day 1)

Suggested, to be challenged:

1. **5 min** — everyone introduces, who owns which layer (Core/Ingestion, Core/Extraction, Core/API+MCP, Revenue App, Second App + Demo)
2. **10 min** — look at the actual dataset Qontext hands us. Update assumptions.
3. **10 min** — lock first commit's architecture: re-confirm or modify [stack.md](stack.md), [data-model.md](data-model.md), [mcp-tools.md](mcp-tools.md). Decide on partner combo (Path A or B).
4. **5 min** — split ownership concretely, agree on shared comms (Discord/WhatsApp), agree on check-in cadence (every 3h?).

---

## 5. Things we explicitly DON'T pre-setup

- Docker — Supabase Cloud is the DB; local mirror via `supabase start` only if needed.
- Database servers — Supabase handles it.
- Cloud accounts beyond partner signups.
- CI/CD — not worth it for 30h.
- Linting/formatting agreements — decide Day 1, whatever ships fast.

---

## 6. Risk register

| Risk | Mitigation |
|---|---|
| Dataset format surprises us | Mock-from-JSON connectors are isolated — can rewrite one in <1h |
| Pioneer fine-tuning takes too long (if Path A) | Fall back to Gemini-only L2; switch to Path B partners |
| Lovable credits run out | Switch to hand-coded shadcn components — we have the skill loaded |
| Live demo fails (source-change → app-update) | Pre-record a backup clip and use a manual "refresh" button as fallback |
| Team sizing (>5 or <3) | Rules cap at 5; below 3 we cut Second App entirely and downscope HITL to manual |
| Aikido finds 50 issues | Triage — submission needs the screenshot, not a perfect score |
| Stage-2 jury is "wow"-driven (Inca/Hera win) | Optimize for track win first; Stage-2 is upside |
