// Canonical data model — aligned with docs/data-model.md
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

export const FACT_STATUS = ['live', 'draft', 'superseded', 'disputed'] as const
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

// ── Core domain models ──────────────────────────────────────────────────────

export interface Entity {
  id: string
  type: EntityType
  canonical_name: string
  aliases: string[]
  attributes: Record<string, unknown>
  status: EntityStatus
  created_at: string
  updated_at: string
  provenance: string[]
}

export interface Fact {
  id: string
  subject: string
  predicate: string
  object: string | number | boolean | null
  object_type: ObjectType
  confidence: number
  status: FactStatus
  derived_from: string[]
  qualifiers: Record<string, unknown>
  created_at: string
  updated_at: string
  superseded_by: string | null
}

export interface Resolution {
  id: string
  conflict_facts: string[]
  decision: ResolutionDecision
  chosen_fact_id: string | null
  qualifier_added: Record<string, unknown> | null
  rationale: string
  resolved_by: string
  resolved_at: string
}

// ── MCP tool response shapes (from docs/mcp-tools.md) ──────────────────────

export interface EntityCard {
  entity: Entity
  facts: Fact[]
  inbound_facts: Fact[]
  related_entities: Array<{
    entity: Entity
    via_predicate: string
    via_fact_id: string
  }>
  vfs_path: string
}

export interface SearchParams {
  query: string
  k?: number
  filter?: {
    entity_types?: EntityType[]
    predicates?: string[]
    min_confidence?: number
    status?: FactStatus[]
    updated_since?: string
  }
}

export interface SearchResult {
  entities: Entity[]
  facts: Fact[]
  files: Array<{ path: string; snippet: string; entity_id: string }>
  query_interpretation: {
    entities_mentioned: string[]
    predicates_mentioned: string[]
    intent: 'lookup' | 'question' | 'browse'
  }
}

export interface ProvenanceEntry {
  source_record_id: string
  evidence_snippet: string
  extractor: 'rule' | 'pioneer' | 'gemini' | 'human'
  extracted_at: string
}

export interface ProvenanceHistory {
  fact: Fact
  provenance: ProvenanceEntry[]
  conflicts?: Fact[]
  supersedes?: string
  superseded_by?: string
}

export interface RecentChangesParams {
  since: string
  entity_ids?: string[]
  kinds?: ChangeKind[]
}

export interface ChangeEvent {
  kind: ChangeKind
  fact_id: string
  entity_id: string
  old_value?: unknown
  new_value: unknown
  triggered_by: string
  at: string
}

export interface ProposeResult {
  status: 'accepted' | 'duplicate' | 'escalated' | 'rejected'
  fact_id?: string
  reason: string
  escalated_to?: { inbox_item_id: string; conflict_with: string[] }
}

export interface FactProposal {
  subject: string
  predicate: string
  object: string | number | boolean | null
  object_type: ObjectType
  confidence: number
  source: { kind: string; description: string; ref?: string }
  qualifiers?: Record<string, unknown>
}

// ── UI utility types ────────────────────────────────────────────────────────

export type ConfidenceLevel = 'high' | 'medium' | 'low' | 'very-low'

// Narrowed type for facts in the conflict inbox
export type DisputedFact = Fact & { status: 'disputed' }
