import { useQuery } from '@tanstack/react-query'
import { getEntity } from '@/lib/api'
import type { EntityCard } from '@/types'

type ApiFact = {
  id: string
  subject_id: string
  predicate: string
  object_id?: string | null
  object_literal?: unknown
  confidence?: number
  status?: string
  derivation?: string
  valid_from?: string
  valid_to?: string | null
  recorded_at?: string
  source_id?: string
  evidence?: Array<{
    source?: string
    record_id?: string | null
    quote?: string | null
    field?: string | null
    confidence?: number | null
  }>
  superseded_by?: string | null
}

type ApiEntityResponse = {
  id: string
  entity_type?: string
  canonical_name?: string
  aliases?: string[]
  attrs?: Record<string, unknown>
  status?: string
  created_at?: string
  updated_at?: string
  trust_score?: number
  fact_count?: number
  source_diversity?: number
  facts?: ApiFact[]
}

function normalizeFactStatus(status: string | undefined): EntityCard['facts'][number]['status'] {
  if (
    status === 'live' ||
    status === 'active' ||
    status === 'draft' ||
    status === 'superseded' ||
    status === 'disputed' ||
    status === 'invalidated' ||
    status === 'needs_refresh'
  ) {
    return status
  }
  return 'live'
}

function normalizeEntityCard(raw: unknown): EntityCard {
  const r = (raw ?? {}) as ApiEntityResponse
  const attrs = r.attrs ?? {}
  const nowIso = new Date(0).toISOString()
  const facts = (r.facts ?? []).map((f) => ({
    id: String(f.id),
    subject_id: String(f.subject_id ?? r.id),
    predicate: String(f.predicate ?? ''),
    object_id: f.object_id ?? null,
    object_literal: f.object_literal ?? null,
    confidence: Number(f.confidence ?? 0),
    derivation: String(f.derivation ?? 'rule'),
    valid_from: f.valid_from ?? nowIso,
    valid_to: f.valid_to ?? null,
    recorded_at: f.recorded_at ?? nowIso,
    source_id: String(f.source_id ?? ''),
    status: normalizeFactStatus(f.status),
    evidence: Array.isArray(f.evidence)
      ? f.evidence.map((ev) => ({
          source: String(ev.source ?? ''),
          record_id: ev.record_id ?? null,
          quote: ev.quote ?? null,
          field: ev.field ?? null,
          confidence: ev.confidence ?? null,
        }))
      : [],
    superseded_by: f.superseded_by ?? null,
  }))

  return {
    id: String(r.id),
    entity_type: String(r.entity_type ?? 'person'),
    canonical_name: String(r.canonical_name ?? r.id ?? ''),
    aliases: Array.isArray(r.aliases) ? r.aliases : [],
    attrs,
    trust_score: Number(r.trust_score ?? 0),
    fact_count: Number(r.fact_count ?? facts.length),
    source_diversity: Number(r.source_diversity ?? 0),
    facts,
  }
}

export function useEntity(entityId: string | null) {
  return useQuery<EntityCard>({
    queryKey: ['entity', entityId],
    queryFn: async () => normalizeEntityCard(await getEntity(entityId!)),
    enabled: !!entityId,
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
}
