import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  decideEntityPair,
  decideFactConflict,
  getTrustWeights,
  listEntityPairResolutions,
  listFactResolutions,
} from '@/lib/api'

export function useEntityPairInbox(status: 'pending' | 'merged' | 'rejected' = 'pending') {
  return useQuery({
    queryKey: ['inbox', 'entity-pairs', status],
    queryFn: () => listEntityPairResolutions(status, 100),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
}

export function useFactConflictInbox(
  status: 'pending' | 'auto_resolved' | 'human_resolved' | 'rejected' = 'pending',
) {
  return useQuery({
    queryKey: ['inbox', 'fact-conflicts', status],
    queryFn: () => listFactResolutions(status, 100),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
}

export function useDecideEntityPair() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      resolutionId,
      decision,
      chosenEntityId,
      decidedBy,
      note,
    }: {
      resolutionId: string
      decision: 'pick_one' | 'merge' | 'reject'
      chosenEntityId?: string
      decidedBy?: string
      note?: string
    }) =>
      decideEntityPair(resolutionId, {
        decision,
        chosen_entity_id: chosenEntityId,
        decided_by: decidedBy,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbox', 'entity-pairs'] })
    },
  })
}

export function useDecideFactConflict() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      resolutionId,
      decision,
      chosenFactId,
      qualifierAdded,
      decidedBy,
      note,
    }: {
      resolutionId: string
      decision: 'pick_one' | 'merge' | 'both_with_qualifier' | 'reject_all'
      chosenFactId?: string
      qualifierAdded?: Record<string, unknown>
      decidedBy?: string
      note?: string
    }) =>
      decideFactConflict(resolutionId, {
        decision,
        chosen_fact_id: chosenFactId,
        qualifier_added: qualifierAdded,
        decided_by: decidedBy,
        note,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbox', 'fact-conflicts'] })
    },
  })
}

export function useTrustWeights() {
  return useQuery({
    queryKey: ['trust-weights'],
    queryFn: getTrustWeights,
    staleTime: 10 * 60_000,
    gcTime: 60 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
  })
}

// ── Pending Types Inbox (Autonome Ontologie-Evolution) ──────────────────────

import { decidePendingType, listPendingTypes } from '@/lib/api'

export function usePendingTypes(kind?: 'entity' | 'edge' | 'source_mapping') {
  return useQuery({
    queryKey: ['inbox', 'pending-types', kind ?? 'all'],
    queryFn: () => listPendingTypes(kind),
    staleTime: 2 * 60_000,
    gcTime: 15 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
}

export function useDecidePendingType() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      pendingId,
      kind,
      decision,
      note,
    }: {
      pendingId: string
      kind: 'entity' | 'edge' | 'source_mapping'
      decision: 'approved' | 'rejected'
      note?: string
    }) => decidePendingType(pendingId, { kind, decision, note }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inbox', 'pending-types'] })
    },
  })
}
