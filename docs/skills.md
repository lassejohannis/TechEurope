# Skill Library (Team)

This repo ships **project-scoped Claude Skills** under `.claude/skills/`. They are committed to git and apply to every team member running Claude Code in the repo. No setup needed — clone + run `claude` and they activate automatically when their triggers match.

The same content is mirrored under `.agents/skills/` for non-Claude tools (Codex, Cursor, GitHub Copilot, Amp, Antigravity, etc.) — added by the `skills` CLI. We keep both so the repo works for any agent tool a team member uses.

## Currently installed

| Skill | What it does | When it triggers |
|---|---|---|
| **supabase** | Supabase domain expertise — Database, Auth, Edge Functions, Realtime, Storage, Vectors, RLS gotchas, security checklist | Any task involving Supabase products, supabase-js, RLS, migrations, the CLI or MCP, or Postgres extensions |
| **supabase-postgres-best-practices** | 30+ reference docs covering RLS, indexing, connection pooling, EXPLAIN ANALYZE, partitioning, JSONB, batch inserts, locks, etc. | Postgres performance, schema design, query optimization, security |
| **shadcn** | Manages shadcn components: adding, searching, fixing, debugging, styling, composing UI. Includes rules for forms, composition, styling, icons, base-vs-radix; CLI + MCP usage; customization patterns | Any project with a `components.json`; shadcn init / `--preset` commands; component-related work |
| **vercel-react-best-practices** | 40+ React/Next.js performance rules across 8 categories from Vercel Engineering | React/Next.js component work, performance optimization, hooks, rendering |
| **web-design-guidelines** | 100+ rules covering accessibility, performance, UX standards. Designed for "audit my UI" / "review my site" workflows | UI review prompts, A11Y audits, pre-submission UI checks |

The Supabase skill includes Anthropic-grade rules on common security traps (e.g. *"never use `user_metadata` for authorization"*, *"views bypass RLS by default"*). Worth reading once even if you never trigger Claude — these are the kind of gotchas that take hours to debug live.

## Where the files live

```
.claude/skills/
├── supabase/
│   ├── SKILL.md                ← the skill body Claude reads
│   ├── references/
│   │   └── skill-feedback.md
│   └── assets/
│       └── feedback-issue-template.md
├── supabase-postgres-best-practices/
│   ├── SKILL.md
│   └── references/             ← ~30 deep-dive markdown files
│       ├── security-rls-basics.md
│       ├── security-rls-performance.md
│       ├── query-missing-indexes.md
│       ├── lock-deadlock-prevention.md
│       └── ... (more)
├── shadcn/
│   ├── SKILL.md
│   ├── cli.md, mcp.md, customization.md
│   ├── rules/                  ← composition rules
│   │   ├── forms.md
│   │   ├── composition.md
│   │   ├── styling.md
│   │   ├── icons.md
│   │   └── base-vs-radix.md
│   └── evals/evals.json
├── vercel-react-best-practices/
│   ├── SKILL.md
│   └── ...                     ← 40+ rules across 8 categories
└── web-design-guidelines/
    ├── SKILL.md
    └── ...                     ← 100+ design / a11y / UX rules
```

`.agents/skills/` mirrors this structure, byte-for-byte.

## Adding more skills

Anyone on the team can add an official skill bundle and commit it:

```bash
# in repo root
npx -y skills@latest add <publisher>/<bundle> --copy --yes
git add .claude/skills .agents/skills
git commit -m "Add <publisher>/<bundle> skills"
git push
```

Important flags:
- `--copy` — installs real files (not symlinks). Required for the skills to survive a clone.
- `--yes` — non-interactive; installs everything in the bundle.

After committing, every teammate gets the skills on their next `git pull`. No re-install needed.

## Removing a skill

```bash
rm -rf .claude/skills/<skill-name> .agents/skills/<skill-name>
git add . && git commit -m "Remove <skill-name>"
```

## Candidates to add during the hack

| Skill | Why we'd add it |
|---|---|
| **anthropic-skills:claude-api** | If anyone on the team writes against the Anthropic SDK |
| **react-best-practices** / **web-design-guidelines** | UI quality during the Revenue App build |
| Custom **`qontext-context-base`** skill (we'd write this) | Auto-load the project's data model + MCP surface into every Claude session, so the team is anchored to our schema |

A custom skill is just a folder under `.claude/skills/<name>/` with a `SKILL.md` that has frontmatter (`name`, `description`) plus body content. We can add one in 10 minutes.

## Security note

Skills run **with full agent permissions** — same as anything in your prompt. The two we installed have been:
- audited by Vercel Labs (Gen Safe)
- 0 alerts from Socket
- Snyk: Med Risk (`supabase`), Low Risk (`supabase-postgres-best-practices`)

Details: https://skills.sh/supabase/agent-skills

For a hackathon repo this is acceptable. For production, review skills before installing.

Risk summary of currently installed skills (from `npx skills add` output):

| Skill | Gen | Socket | Snyk |
|---|---|---|---|
| supabase | Safe | 0 alerts | Med |
| supabase-postgres-best-practices | Safe | 0 alerts | Low |
| shadcn | Safe | 0 alerts | Med |
| vercel-react-best-practices | Safe | 0 alerts | Low |
| web-design-guidelines | Safe | 0 alerts | Low |

## Note: vercel-labs/agent-skills bundle has 7 skills, we kept 2

The `vercel-labs/agent-skills` bundle contains 7 skills total. We installed only the 2 that fit our 30h Vite+React+shadcn UI work:

- **vercel-react-best-practices** ✓ kept
- **web-design-guidelines** ✓ kept
- ~~deploy-to-vercel~~ — we're not deploying to Vercel
- ~~vercel-cli-with-tokens~~ — same
- ~~vercel-composition-patterns~~ — overlap with shadcn skill
- ~~vercel-react-native-skills~~ — web only
- ~~vercel-react-view-transitions~~ — out of scope

If we want any back, run `npx skills add vercel-labs/agent-skills --copy` and pick interactively (or `--yes` to grab everything).
