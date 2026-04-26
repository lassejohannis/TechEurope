# Aikido

**Side-Prize**: 1 000 €.
**Pflicht-Partner**: ❌ explicitly excluded from the required-3 (per hackathon rules).

## Status: evaluated, configured, not gating CI

We treat Aikido as a security hygiene layer, not a build-block. The repo has the configuration in place; findings are visible to the team but don't fail the pipeline (Hackathon-Friday code is sometimes ugly and we'd rather ship + fix than block).

## What it covers

When configured Aikido runs:
- **SCA** — dependency vulnerability scanning across `pyproject.toml`, `package.json`, `csm-app/package.json`, `web/package.json`.
- **SAST** — static-analysis findings on Python + TypeScript.
- **Secrets** — token / API-key leak detection in commits (paired with our `.gitignore` discipline around `.env` and `NOTES.local.md`).
- **IaC** — Supabase migrations checked for missing RLS, `set search_path` issues.

## How we use the findings

- Triage in the Aikido dashboard once per day during the hackathon.
- Fix critical/high severity inline (e.g., we caught a Postgres `SECURITY DEFINER` view issue early and added `set search_path = ''` per the Supabase best-practices skill).
- Ignore low-severity vendored-deps findings until post-submission.

## What we already addressed (visible in code)

- `.env` and `NOTES.local.md` are gitignored — no secret-leak commits.
- `web/.env.example` ships with placeholders, never real keys.
- Supabase RLS on production tables follows the patterns from `.claude/skills/supabase-postgres-best-practices/`.
- `agent_tokens` are stored as bcrypt hashes (`server/src/server/auth/tokens.py:_hash`) — plain-text returned only once at issue-time.

## Side-Prize criteria (self-assessed)

| Kriterium | Status | Evidence |
|---|---|---|
| Configured + integrated | ⚠️ partial | Configured for the project; CI gating turned off intentionally |
| Real findings addressed | ✅ | Search-path hardening, bcrypt token storage, gitignore discipline |
| Documented usage | ✅ | This file |
| End-to-end "Aikido report → fix → commit" loop | ⚠️ | We worked through the dashboard but didn't tag PRs with Aikido issue IDs |

## Honesty notes

Aikido is the partner with the loosest integration in this repo. The hackathon rules explicitly exclude it from the required-3, which means we prioritized our 3 code-deep partners (Gemini, Pioneer, Tavily) and treated Aikido as a hygiene layer rather than a story.

If we had another half-day, we would:
- Write a small `aikido-summary.md` that pulls the latest dashboard JSON and tabulates findings per-severity.
- Wire `aikido-cli` into the pre-commit hook so secrets are caught at `git add` time rather than after-the-fact.

## Demo snippet

```bash
# Sample aikido-cli usage if installed locally
aikido scan --project tech-europe-qontext

# Our gitignore tells the story too
cat .gitignore | grep -E "env|secret|token"
```
