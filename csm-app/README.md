# Qontext CSM App

A Customer Success Manager application for the Qontext / Emidat platform. CSMs use this app to monitor account health, review daily briefings, and prepare for customer meetings.

## What it is

The CSM app surfaces account intelligence derived from the Qontext Context Layer: health scores, sentiment trends, renewal risk signals, open tickets, and communication history — all in one view per account. A daily briefing page groups AI-generated alerts by priority so CSMs know exactly where to focus each day.

## Running locally

```bash
cd TechEurope/csm-app
npm install
npm run dev
```

App runs at **http://localhost:5174**

## Architecture

```
src/
  types/index.ts          — Domain types (mirrors Context Layer API shapes exactly)
  lib/
    api.ts                — API client (mock mode by default)
    mocks/acme.ts         — All mock data (same field names and types as real API)
  store/ui.ts             — Zustand UI state
  hooks/
    useAccount.ts         — React Query hook for single account
    useAccounts.ts        — React Query hook for account list
    useBriefing.ts        — React Query hook for daily briefing
  components/
    layout/
      AppShell.tsx        — Root layout with <Outlet>
      TopBar.tsx          — Navigation bar with account tabs
    common/
      HealthBadge.tsx     — Red / yellow / green tier badge
      SentimentChip.tsx   — Renders API-provided sentiment annotation
      PriorityCard.tsx    — Briefing item card with signal chip
  pages/
    briefing/BriefingPage.tsx   — Daily briefing grouped by priority
    account/
      AccountPage.tsx     — Two-column account view
      HealthScore.tsx     — Score number + factor list
      Timeline.tsx        — Merged communication + ticket feed
      MeetingBrief.tsx    — Pre-meeting talking points from account data
```

## Mock Data

**Location:** `src/lib/mocks/acme.ts`

**Sentinel:** `USE_MOCK = true` in `src/lib/api.ts` — set to `false` when the real Context Layer API is live. Only `src/lib/api.ts` changes; zero app code changes needed.

**Accounts covered:**

| Account | ID | Health | Notes |
|---|---|---|---|
| ACME GmbH | `ent:acme` | 58 / Yellow | Disputed renewal, open price ticket INZ-8821, expansion interest signal |
| Meridian Robotics | `ent:meridian` | 82 / Green | SSO rollout on track, 80-seat expansion ask, new procurement lead |
| Northstar Energy | `ent:northstar` | 44 / Red | 45 days no response, low platform usage, September renewal |

**Sentiment fields** in mock data represent what the Gemini sentiment pipeline would return. The app code only reads these fields — it never computes, assigns, or derives sentiment values. `Communication.sentiment` and `Ticket.sentiment` are `SentimentAnnotation | null`; null means the pipeline has not yet run on that record.

**Daily Briefing** contains 6 items:
- RED: ACME renewal_risk, ACME sentiment_drop, Northstar engagement_gap
- YELLOW: ACME ticket_spike, Meridian stakeholder_change
- GREEN: Meridian upsell_signal

## Context Layer API

When `USE_MOCK = false`, the client expects these endpoints on `http://localhost:8000`:

| Method | Path | Returns |
|---|---|---|
| GET | `/api/accounts` | `Array<{ id, name, health_tier }>` |
| GET | `/api/accounts/:id` | `AccountCard` |
| GET | `/api/briefing/daily` | `DailyBriefing` |

All response shapes are defined in `src/types/index.ts`. The server must populate `sentiment` fields on `Communication` and `Ticket` objects (via Gemini pipeline); the client reads them as-is.

## Design system

- CSS custom properties defined in `src/index.css` (`--brand`, `--conf-high`, etc.)
- No Tailwind utility classes in component CSS — only CSS class names using `var()` tokens
- Tailwind `@theme inline {}` tokens map Tailwind color utilities to the same CSS vars
- Port: **5174** (sibling `web/` app uses 5173)
