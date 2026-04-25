// Canonical data model — aligned with actual backend API responses.
// No enum keyword (TS 6.0 erasableSyntaxOnly). Use const + type union throughout.

export const ENTITY_TYPES = [
  'person',
  'customer',
  'product',
  'org_unit',
  'process',
  'policy',
  'project',
  'task',
  'ticket',
  'document',
  'communication',
] as const
export type EntityType = (typeof ENTITY_TYPES)[number]

export const ENTITY_STATUS = ['live', 'draft', 'archived'] as const
export type EntityStatus = (typeof ENTITY_STATUS)[number]

export const FACT_STATUS = ['live', 'active', 'draft', 'superseded', 'disputed', 'invalidated', 'needs_refresh'] as const
export type FactStatus = (typeof FACT_STATUS)[number]

export const OBJECT_TYPES = ['entity', 'string', 'number', 'date', 'bool', 'enum'] as const
export type ObjectType = (typeof OBJECT_TYPES)[number]

export const RESOLUTION_DECISIONS = [
  'pick_one',
  'merge',
  'both_with_qualifier',
  'reject_all',
] as const
export type ResolutionDecision = (typeof RESOLUTION_DECISIONS)[number]

export const CHANGE_KINDS = [
  'created',
  'updated',
  'superseded',
  'disputed',
  'resolved',
] as const
export type ChangeKind = (typeof CHANGE_KINDS)[number]

// ── Backend response shapes ──────────────────────────────────────────────────
// These match what FastAPI actually returns (server/src/server/models.py)

export interface EvidenceItem {
  source: string
  record_id: string | null
  quote: string | null
  field: string | null
  confidence: number | null
}

export interface SourceReference {
  system: string
  path: string | null
  record_id: string | null
  timestamp: string | null
  method: string
}

// Matches FactResponse in models.py
export interface Fact {
  id: string
  subject_id: string
  predicate: string
  object_id: string | null
  object_literal: unknown | null
  confidence: number
  derivation: string
  valid_from: string
  valid_to: string | null
  recorded_at: string
  source_id: string
  status: FactStatus
  evidence: EvidenceItem[]
  superseded_by?: string | null
}

// Matches EntityResponse in models.py
export interface Entity {
  id: string
  entity_type: EntityType | string
  canonical_name: string
  aliases: string[]
  attrs: Record<string, unknown>
  trust_score: number
  fact_count: number
  source_diversity: number
  facts: Fact[]
}

// Matches ProvenanceResponse in models.py — returned by GET /api/facts/{id}/provenance
export interface ProvenanceResponse {
  fact: Fact
  source_reference: SourceReference
  superseded_by: Fact | null
  trust_weight: number
}

// Matches what GET /api/entities/{id} returns
export interface EntityCard {
  id: string
  entity_type: EntityType | string
  canonical_name: string
  aliases: string[]
  attrs: Record<string, unknown>
  trust_score: number
  fact_count: number
  source_diversity: number
  facts: Fact[]
}

// Matches SearchResponse in models.py — returned by POST /api/search
export interface SearchResultItem {
  entity: Entity
  score: number
  match_type: 'semantic' | 'structural' | 'hybrid'
  evidence: EvidenceItem[]
}

export interface SearchResponse {
  query: string
  results: SearchResultItem[]
  total: number
}

// Matches fact_changes row returned by GET /api/changes/recent
export interface ChangeEvent {
  id: number
  kind: string
  fact_id: string | null
  old_value: unknown | null
  new_value: unknown | null
  triggered_by: string | null
  at: string
}

// Matches ProposeFactRequest in models.py — body for POST /api/vfs/propose-fact
export interface FactProposal {
  subject_id: string
  predicate: string
  object_id?: string | null
  object_literal?: unknown | null
  confidence: number
  source_system: string
  source_method: string
  note?: string | null
}

// Matches ProposeFactResponse in models.py
export interface ProposeResult {
  fact_id: string
  source_record_id: string
  status: string
}

// Params for the recent changes feed
export interface RecentChangesParams {
  limit?: number
}

// Search request body — matches SearchRequest in models.py
export interface SearchParams {
  query: string
  k?: number
  as_of?: string | null
  entity_type?: string | null
}

// Resolution in resolutions table
export interface Resolution {
  id: string
  entity_id_1: string
  entity_id_2: string
  status: string
  resolution_signals: Record<string, unknown>
  decided_at: string | null
  decided_by: string | null
}

// ── UI utility types ────────────────────────────────────────────────────────

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'very-low'

export type DisputedFact = Fact & { status: 'disputed' }

// Legacy aliases — kept so components that haven't been updated yet still compile.
// Remove once all components are migrated.
/** @deprecated Use Entity instead */
export type EntityLegacy = Entity
/** @deprecated Use ProvenanceResponse instead */
export type ProvenanceHistory = ProvenanceResponse
/** @deprecated Use SearchResponse instead */
export type SearchResult = SearchResponse
