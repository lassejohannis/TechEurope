import type {
  EntityCard,
  SearchParams,
  SearchResponse,
  ProvenanceResponse,
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

export function searchMemory(params: SearchParams): Promise<SearchResponse> {
  return apiFetch<SearchResponse>('/api/search', {
    method: 'POST',
    body: JSON.stringify(params),
  })
}

// GET /api/entities/{id}?as_of=<iso>
// Returns EntityCard (entity_type, attrs, trust_score, facts[])
export function getEntity(entityId: string, asOf?: string): Promise<EntityCard> {
  const qs = asOf ? `?as_of=${encodeURIComponent(asOf)}` : ''
  return apiFetch<EntityCard>(`/api/entities/${encodeURIComponent(entityId)}${qs}`)
}

// GET /api/facts/{id}/provenance
// Returns ProvenanceResponse (fact, source_reference, superseded_by, trust_weight)
export function getFact(factId: string): Promise<ProvenanceResponse> {
  return apiFetch<ProvenanceResponse>(
    `/api/facts/${encodeURIComponent(factId)}/provenance`,
  )
}

// GET /api/changes/recent?limit=N
// Returns { changes: ChangeEvent[], total: number }
export function listRecentChanges(
  params: RecentChangesParams,
): Promise<{ changes: ChangeEvent[]; total: number }> {
  const limit = params.limit ?? 50
  return apiFetch(`/api/changes/recent?limit=${limit}`)
}

// ── Write operations ─────────────────────────────────────────────────────────

// POST /api/vfs/propose-fact
// Body: FactProposal (subject_id, predicate, object_literal, confidence, source_system, source_method)
export function proposeFact(proposal: FactProposal): Promise<ProposeResult> {
  return apiFetch<ProposeResult>('/api/vfs/propose-fact', {
    method: 'POST',
    body: JSON.stringify(proposal),
  })
}

// PATCH /api/vfs/{path}
// Update entity attrs without touching facts
export function patchVfsNode(
  path: string,
  attrs: Record<string, unknown>,
  reason?: string,
): Promise<{ path: string; entity_id: string; attrs_updated: string[]; attrs_removed: string[] }> {
  return apiFetch(`/api/vfs/${path.replace(/^\//, '')}`, {
    method: 'PATCH',
    body: JSON.stringify({ attrs, reason }),
  })
}

// DELETE /api/vfs/{path}?reason=...
export function deleteVfsNode(
  path: string,
  reason?: string,
): Promise<{ deleted_path: string; facts_invalidated: number; audit_record: string }> {
  const qs = reason ? `?reason=${encodeURIComponent(reason)}` : ''
  return apiFetch(`/api/vfs/${path.replace(/^\//, '')}${qs}`, { method: 'DELETE' })
}

// POST /api/resolutions/{id}/decide  (WS-5 — backend not yet implemented)
export function resolveConflict(
  resolutionId: string,
  decision: { decision: string; decided_by?: string; note?: string },
): Promise<void> {
  return apiFetch<void>(`/api/resolutions/${encodeURIComponent(resolutionId)}/decide`, {
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

// ── Pending Types Inbox ──────────────────────────────────────────────────────

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

// POST /api/facts/{id}/edit — supersede a fact with a new value (bi-temporal)
export function editFact(
  factId: string,
  body: { object_id?: string; object_literal?: unknown; confidence?: number; note?: string },
): Promise<ProposeResult> {
  return apiFetch<ProposeResult>(`/api/facts/${encodeURIComponent(factId)}/edit`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// POST /api/facts/{id}/flag — mark a fact as disputed
export function flagFact(factId: string, reason: string): Promise<void> {
  return apiFetch<void>(`/api/facts/${encodeURIComponent(factId)}/flag`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
  })
}

// POST /api/facts/{id}/validate — human-validate a fact
export function validateFact(factId: string, note?: string): Promise<void> {
  return apiFetch<void>(`/api/facts/${encodeURIComponent(factId)}/validate`, {
    method: 'POST',
    body: JSON.stringify({ note }),
  })
}

// POST /api/webhooks/source-change — trigger needs_refresh on a source record
export function notifySourceChange(sourceRecordId: string): Promise<{ marked_stale: number }> {
  return apiFetch('/api/webhooks/source-change', {
    method: 'POST',
    body: JSON.stringify({ source_record_id: sourceRecordId }),
  })
}
