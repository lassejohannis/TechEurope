import type { AccountCard, DailyBriefing } from '@/types'
import { MOCK_ACCOUNT_CARDS, MOCK_BRIEFING } from '@/lib/mocks/acme'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''
const USE_MOCK = true  // flip to false when Context Layer API is live

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

export async function getAccountCard(accountId: string): Promise<AccountCard> {
  if (USE_MOCK) {
    const card = MOCK_ACCOUNT_CARDS[accountId]
    if (!card) throw new ApiError(404, `No mock data for account ${accountId}`)
    return Promise.resolve(card)
  }
  return apiFetch<AccountCard>(`/api/accounts/${encodeURIComponent(accountId)}`)
}

export async function getDailyBriefing(): Promise<DailyBriefing> {
  if (USE_MOCK) return Promise.resolve(MOCK_BRIEFING)
  return apiFetch<DailyBriefing>('/api/briefing/daily')
}

export async function listAccounts(): Promise<Array<{ id: string; name: string; health_tier: 'red' | 'yellow' | 'green' }>> {
  if (USE_MOCK) {
    return Promise.resolve(
      Object.values(MOCK_ACCOUNT_CARDS).map((c) => ({
        id: c.entity.id,
        name: c.entity.canonical_name,
        health_tier: c.health.tier,
      }))
    )
  }
  return apiFetch('/api/accounts')
}
