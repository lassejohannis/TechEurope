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

// ── Conflict Inbox ──────────────────────────────────────────────────────────

export interface EntityPairInboxItem {
  id: string
  entity_id_1: string
  entity_id_2: string
  status: string
  resolution_signals: Record<string, unknown>
  decided_at: string | null
  decided_by: string | null
  created_at: string
  entity_1: { id: string; entity_type: string; canonical_name: string; attrs: Record<string, unknown> } | null
  entity_2: { id: string; entity_type: string; canonical_name: string; attrs: Record<string, unknown> } | null
}

export interface FactConflictInboxItem {
  id: string
  conflict_facts: string[]
  status: string
  decision: string | null
  chosen_fact_id: string | null
  rationale: string | null
  resolved_at: string | null
  resolved_by: string | null
  facts: Array<{
    id: string
    subject_id: string
    predicate: string
    object_id: string | null
    object_literal: unknown
    confidence: number
    source_id: string
    valid_from: string
    recorded_at: string
    status: string
    source: { id: string; source_type: string; source_uri: string | null } | null
  }>
}

export interface InboxResponse<T> {
  items: T[]
  total: number
}

export function listEntityPairResolutions(
  status: 'pending' | 'merged' | 'rejected' = 'pending',
  limit = 50,
): Promise<InboxResponse<EntityPairInboxItem>> {
  return apiFetch(`/api/resolutions?status=${status}&limit=${limit}`)
}

export function listFactResolutions(
  status: 'pending' | 'auto_resolved' | 'human_resolved' | 'rejected' = 'pending',
  limit = 50,
): Promise<InboxResponse<FactConflictInboxItem>> {
  return apiFetch(`/api/fact-resolutions?status=${status}&limit=${limit}`)
}

export function decideEntityPair(
  resolutionId: string,
  body: {
    decision: 'pick_one' | 'merge' | 'reject'
    chosen_entity_id?: string
    decided_by?: string
    note?: string
  },
): Promise<{ status: string; winner_id: string | null }> {
  return apiFetch(`/api/resolutions/${encodeURIComponent(resolutionId)}/decide`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function decideFactConflict(
  resolutionId: string,
  body: {
    decision: 'pick_one' | 'merge' | 'both_with_qualifier' | 'reject_all'
    chosen_fact_id?: string
    qualifier_added?: Record<string, unknown>
    decided_by?: string
    note?: string
  },
): Promise<{ status: string; chosen_fact_id: string | null }> {
  return apiFetch(`/api/fact-resolutions/${encodeURIComponent(resolutionId)}/decide`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getTrustWeights(): Promise<{ weights: Record<string, number> }> {
  return apiFetch('/api/trust-weights')
}

// ── Pending Types Inbox (Autonome Ontologie-Evolution) ──────────────────────

export interface PendingTypeItem {
  id: string
  kind: 'entity' | 'edge' | 'source_mapping'
  config?: Record<string, unknown>
  approval_status?: string
  status?: string
  auto_proposed?: boolean
  proposed_by_source_id?: string | null
  similarity_to_nearest?: number | null
  proposal_rationale?: string | null
  rationale?: string | null
  from_type?: string | null
  to_type?: string | null
  source_type?: string
  mapping_version?: number
  validation_stats?: Record<string, unknown>
  created_from_sample_ids?: string[]
  proposed_at?: string
}

export function listPendingTypes(
  kind?: 'entity' | 'edge' | 'source_mapping',
  limit = 50,
): Promise<{ items: PendingTypeItem[]; total: number; kind_filter: string | null }> {
  const params = new URLSearchParams()
  if (kind) params.set('kind', kind)
  params.set('limit', String(limit))
  return apiFetch(`/api/admin/pending-types?${params.toString()}`)
}

export function decidePendingType(
  pendingId: string,
  body: {
    kind: 'entity' | 'edge' | 'source_mapping'
    decision: 'approved' | 'rejected'
    note?: string
  },
): Promise<{ id: string; kind: string; decision: string; decided_by: string }> {
  return apiFetch(`/api/admin/pending-types/${encodeURIComponent(pendingId)}/decide`, {
    method: 'POST',
    body: JSON.stringify(body),
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
