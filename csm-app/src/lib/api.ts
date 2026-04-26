import type { AccountCard, AccountInsight, CardSummary, DailyBriefing, EmailDraft, EscalationBriefing } from '@/types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) throw new ApiError(res.status, `API ${res.status}: ${res.statusText}`)
  return res.json() as Promise<T>
}

// ── Account data ──────────────────────────────────────────────────────────────
// Real endpoint: GET /api/accounts/:id

export async function getAccountCard(accountId: string): Promise<AccountCard> {
  return apiFetch<AccountCard>(`/api/accounts/${encodeURIComponent(accountId)}`)
}

// Real endpoint: GET /api/accounts

export async function listAccounts(): Promise<AccountCard[]> {
  return apiFetch<AccountCard[]>('/api/accounts')
}

// ── Daily briefing ────────────────────────────────────────────────────────────
// Real endpoint: GET /api/briefing/daily

export async function getDailyBriefing(): Promise<DailyBriefing> {
  return apiFetch<DailyBriefing>('/api/briefing/daily')
}

// ── Card summaries ────────────────────────────────────────────────────────────
// Real endpoint: GET /api/briefing/summaries
// Demo: returns Gemini-generated summaries cached in mock file

export async function getCardSummaries(): Promise<Record<string, CardSummary>> {
  return apiFetch<Record<string, CardSummary>>('/api/briefing/summaries')
}

// ── Generated email drafts ────────────────────────────────────────────────────
// Real endpoint: POST /api/generate/recovery-email
// Demo: returns cached draft from mock file (variation cycles through 2 options)

export async function generateRecoveryEmail(accountId: string, variation: number): Promise<EmailDraft> {
  return apiFetch<EmailDraft>('/api/generate/recovery-email', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, variation }),
  })
}

// Real endpoint: POST /api/generate/stakeholder-intro
// Demo: returns cached draft from mock file

export async function generateStakeholderIntroEmail(accountId: string, contactId: string): Promise<EmailDraft> {
  return apiFetch<EmailDraft>('/api/generate/stakeholder-intro', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId, contact_id: contactId }),
  })
}

// Real endpoint: POST /api/generate/escalation-briefing
// Demo: returns cached briefing from mock file

export async function generateEscalationBriefing(accountId: string): Promise<EscalationBriefing> {
  return apiFetch<EscalationBriefing>('/api/generate/escalation-briefing', {
    method: 'POST',
    body: JSON.stringify({ account_id: accountId }),
  })
}

// Real endpoint: GET /api/accounts/:id/insights
// Demo: returns pre-computed insights derived from facts/tickets/comms per account

export async function getAccountInsights(accountId: string): Promise<AccountInsight[]> {
  return apiFetch<AccountInsight[]>(`/api/accounts/${encodeURIComponent(accountId)}/insights`)
}
