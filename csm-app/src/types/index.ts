export const ENTITY_TYPES = [
  'person', 'customer', 'product', 'org_unit', 'process',
  'policy', 'project', 'task', 'ticket', 'document', 'communication',
] as const
export type EntityType = typeof ENTITY_TYPES[number]

export const FACT_STATUS = ['live', 'draft', 'superseded', 'disputed'] as const
export type FactStatus = typeof FACT_STATUS[number]

export const SENTIMENT_LABELS = ['positive', 'neutral', 'negative', 'mixed'] as const
export type SentimentLabel = typeof SENTIMENT_LABELS[number]

// Sentiment always comes from API — never computed in app code
export interface SentimentAnnotation {
  sentiment_label: SentimentLabel
  sentiment_score: number        // -1.0 to 1.0
  confidence: number             // 0.0 to 1.0
  aspects: Array<{ topic: string; label: SentimentLabel; score: number }>
}

export interface Entity {
  id: string
  type: EntityType
  canonical_name: string
  aliases: string[]
  attributes: Record<string, unknown>
  status: 'live' | 'draft' | 'archived'
  created_at: string
  updated_at: string
  provenance: string[]
}

export interface Fact {
  id: string
  subject: string
  predicate: string
  object: string | number | boolean | null
  object_type: 'entity' | 'string' | 'number' | 'date' | 'bool' | 'enum'
  confidence: number
  status: FactStatus
  derived_from: string[]
  qualifiers: Record<string, unknown>
  created_at: string
  updated_at: string
  superseded_by: string | null
}

export interface Communication {
  id: string
  subject: string
  body_snippet: string
  from_address: string
  to_addresses: string[]
  date: string
  source_type: 'email' | 'chat' | 'call_transcript'
  linked_entity_ids: string[]
  sentiment: SentimentAnnotation | null   // null = pipeline hasn't run
  extracted_fact_ids: string[]
}

export interface Ticket {
  id: string
  external_id: string
  title: string
  status: 'open' | 'in_progress' | 'resolved' | 'closed'
  priority: 'low' | 'medium' | 'high' | 'critical'
  created_at: string
  updated_at: string
  resolved_at: string | null
  linked_entity_ids: string[]
  sentiment: SentimentAnnotation | null
}

export interface AccountHealth {
  score: number              // 0–100
  tier: 'red' | 'yellow' | 'green'
  factors: Array<{
    name: string
    value: string | number
    trend: 'up' | 'down' | 'flat'
    weight: number
  }>
  computed_at: string
}

export interface AccountCard {
  entity: Entity
  facts: Fact[]
  key_contacts: Array<{ entity: Entity; role: string }>
  open_tickets: Ticket[]
  recent_communications: Communication[]
  health: AccountHealth
}

export const SIGNAL_TYPES = [
  'sentiment_drop', 'renewal_risk', 'stakeholder_change',
  'ticket_spike', 'engagement_gap', 'upsell_signal',
] as const
export type SignalType = typeof SIGNAL_TYPES[number]

export interface BriefingItem {
  id: string
  account_id: string
  account_name: string
  priority: 'red' | 'yellow' | 'green'
  signal_type: SignalType
  headline: string
  detail: string
  recommended_action: string
  evidence_fact_ids: string[]
  communication_id: string | null
  created_at: string
}

export interface DailyBriefing {
  generated_at: string
  items: BriefingItem[]
  summary: string
}
