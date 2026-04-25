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
  facts?: ApiFact[]
}

function normalizeFactObject(value: unknown): string | number | boolean | null {
  if (value == null) return null
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') return value
  return JSON.stringify(value)
}

function normalizeEntityCard(raw: unknown): EntityCard {
  const r = (raw ?? {}) as ApiEntityResponse
  const attrs = r.attrs ?? {}
  const facts = (r.facts ?? []).map((f) => ({
    id: String(f.id),
    subject: String(f.subject_id),
    predicate: String(f.predicate ?? ''),
    object: normalizeFactObject(f.object_literal ?? f.object_id ?? null),
    object_type: 'string' as const,
    confidence: Number(f.confidence ?? 0),
    status: (f.status === 'draft' || f.status === 'superseded' || f.status === 'disputed' || f.status === 'live'
      ? f.status
      : 'live') as 'draft' | 'superseded' | 'disputed' | 'live',
    derived_from: [],
    qualifiers: {},
    created_at: r.created_at ?? new Date(0).toISOString(),
    updated_at: r.updated_at ?? new Date(0).toISOString(),
    superseded_by: null,
  }))

  return {
    entity: {
      id: String(r.id),
      type: String(r.entity_type ?? 'person') as EntityCard['entity']['type'],
      canonical_name: String(r.canonical_name ?? r.id ?? ''),
      aliases: Array.isArray(r.aliases) ? r.aliases : [],
      attributes: attrs,
      status: (r.status === 'draft' || r.status === 'archived' || r.status === 'live' ? r.status : 'live'),
      created_at: r.created_at ?? new Date(0).toISOString(),
      updated_at: r.updated_at ?? new Date(0).toISOString(),
      provenance: [],
    },
    facts,
    inbound_facts: [],
    related_entities: [],
    vfs_path: String((attrs.vfs_path as string | undefined) ?? `/entities/${r.id}`),
  }
}

export function useEntity(entityId: string | null) {
  return useQuery<EntityCard>({
    queryKey: ['entity', entityId],
    queryFn: async () => normalizeEntityCard(await getEntity(entityId!)),
    enabled: !!entityId,
  })
}
