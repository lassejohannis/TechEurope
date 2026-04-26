import type {
  EntityCard,
  SearchParams,
  SearchResponse,
  ProvenanceResponse,
  RecentChangesParams,
  ChangeEvent,
  ProposeResult,
  FactProposal,
  EntityProvenanceResponse,
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

// GET /api/entities/{id}/provenance
export function getEntityProvenance(entityId: string): Promise<EntityProvenanceResponse> {
  return apiFetch<EntityProvenanceResponse>(`/api/entities/${encodeURIComponent(entityId)}/provenance`)
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

// POST /api/entities/{id}/edit
export function editEntity(
  entityId: string,
  body: { canonical_name?: string; attrs?: Record<string, unknown>; reason?: string },
): Promise<{ entity_id: string; updated: boolean; updated_fields?: string[]; audit_record?: string }> {
  return apiFetch(`/api/entities/${encodeURIComponent(entityId)}/edit`, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

// POST /api/entities/{id}/link-entity
export function linkEntity(
  entityId: string,
  body: {
    predicate: string
    target_entity_type: string
    target_canonical_name: string
    target_attrs?: Record<string, unknown>
    confidence?: number
    reason?: string
  },
): Promise<{ fact_id: string; target_entity_id: string; source_record_id: string; status: string }> {
  return apiFetch(`/api/entities/${encodeURIComponent(entityId)}/link-entity`, {
    method: 'POST',
    body: JSON.stringify(body),
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
    extraction_confidence?: number
    verification_score?: number
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
  limit?: number | null
  offset?: number | null
}

export function listEntityPairResolutions(
  status: 'pending' | 'merged' | 'rejected' = 'pending',
  limit?: number,
  offset?: number,
): Promise<InboxResponse<EntityPairInboxItem>> {
  const params = new URLSearchParams()
  params.set('status', status)
  if (typeof limit === 'number') params.set('limit', String(limit))
  if (typeof offset === 'number') params.set('offset', String(offset))
  return apiFetch(`/api/resolutions?${params.toString()}`)
}

export function listFactResolutions(
  status: 'pending' | 'auto_resolved' | 'human_resolved' | 'rejected' = 'pending',
  limit?: number,
  offset?: number,
): Promise<InboxResponse<FactConflictInboxItem>> {
  const params = new URLSearchParams()
  params.set('status', status)
  if (typeof limit === 'number') params.set('limit', String(limit))
  if (typeof offset === 'number') params.set('offset', String(offset))
  return apiFetch(`/api/fact-resolutions?${params.toString()}`)
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

// POST /api/facts/{id}/delete — invalidate a fact
export function deleteFact(factId: string, reason?: string): Promise<void> {
  return apiFetch<void>(`/api/facts/${encodeURIComponent(factId)}/delete`, {
    method: 'POST',
    body: JSON.stringify({ reason }),
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

// ── Connect: agent token issuance ────────────────────────────────────────────

export type IssuedToken = {
  token: string
  token_id: string
  name: string
  scopes: string[]
}

export function issueAgentToken(name: string, scopes: string[]): Promise<IssuedToken> {
  return apiFetch<IssuedToken>('/api/admin/tokens', {
    method: 'POST',
    body: JSON.stringify({ name, scopes }),
  })
}
