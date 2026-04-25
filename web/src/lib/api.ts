import type {
  EntityCard,
  SearchParams,
  SearchResult,
  ProvenanceHistory,
  RecentChangesParams,
  ChangeEvent,
  ProposeResult,
  FactProposal,
} from '@/types'

const BASE = import.meta.env.VITE_API_BASE_URL ?? ''

export class ApiError extends Error {
  readonly status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    throw new ApiError(res.status, `API ${res.status}: ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

// ── Read operations ──────────────────────────────────────────────────────────

export function searchMemory(params: SearchParams): Promise<SearchResult> {
  return apiFetch<SearchResult>('/api/search', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export function getEntity(entityId: string): Promise<EntityCard> {
  return apiFetch<EntityCard>(`/api/entities/${encodeURIComponent(entityId)}`)
}

export function getFact(factId: string): Promise<ProvenanceHistory> {
  return apiFetch<ProvenanceHistory>(
    `/api/facts/${encodeURIComponent(factId)}/provenance`,
  )
}

export function listRecentChanges(
  params: RecentChangesParams,
): Promise<{ changes: ChangeEvent[]; cursor?: string }> {
  return apiFetch('/api/changes', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

export function getProvenance(entityId: string): Promise<ProvenanceHistory[]> {
  return apiFetch<ProvenanceHistory[]>(
    `/api/entities/${encodeURIComponent(entityId)}/provenance`,
  )
}

// ── Write operations ─────────────────────────────────────────────────────────

export function proposeFact(proposal: FactProposal): Promise<ProposeResult> {
  return apiFetch<ProposeResult>('/api/facts/propose', {
    method: 'POST',
    body: JSON.stringify(proposal),
  })
}

export function flagFact(factId: string, reason: string): Promise<void> {
  return apiFetch<void>('/api/facts/flag', {
    method: 'POST',
    body: JSON.stringify({ fact_id: factId, reason }),
  })
}

export function resolveConflict(
  conflictId: string,
  decision: { resolution: string; chosen_fact_id?: string; rationale?: string },
): Promise<void> {
  return apiFetch<void>(`/api/conflicts/${encodeURIComponent(conflictId)}/resolve`, {
    method: 'POST',
    body: JSON.stringify(decision),
  })
}

export function editProperty(
  entityId: string,
  factId: string,
  newValue: unknown,
): Promise<ProposeResult> {
  return apiFetch<ProposeResult>('/api/facts/propose', {
    method: 'POST',
    body: JSON.stringify({
      subject: entityId,
      object: newValue,
      source: { kind: 'manual_entry', description: `Edit via UI: fact ${factId}`, ref: factId },
      confidence: 1.0,
    }),
  })
}
