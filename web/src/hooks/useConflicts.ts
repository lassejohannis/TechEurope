import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  decideEntityPair,
  decideFactConflict,
  getTrustWeights,
  listEntityPairResolutions,
  listFactResolutions,
  refreshBrowseTree,
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

export function useEntityPairInboxInfinite(
  status: 'pending' | 'merged' | 'rejected' = 'pending',
  pageSize = 100,
) {
  return useInfiniteQuery({
    queryKey: ['inbox', 'entity-pairs-infinite', status, pageSize],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listEntityPairResolutions(status, pageSize, pageParam),
    getNextPageParam: (lastPage) => {
      const loaded = (lastPage.offset ?? 0) + lastPage.items.length
      if (loaded >= lastPage.total) return undefined
      return loaded
    },
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
  })
}

export function useFactConflictInboxInfinite(
  status: 'pending' | 'auto_resolved' | 'human_resolved' | 'rejected' = 'pending',
  pageSize = 100,
) {
  return useInfiniteQuery({
    queryKey: ['inbox', 'fact-conflicts-infinite', status, pageSize],
    initialPageParam: 0,
    queryFn: ({ pageParam }) => listFactResolutions(status, pageSize, pageParam),
    getNextPageParam: (lastPage) => {
      const loaded = (lastPage.offset ?? 0) + lastPage.items.length
      if (loaded >= lastPage.total) return undefined
      return loaded
    },
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
      qc.invalidateQueries({ queryKey: ['inbox', 'entity-pairs-infinite'] })
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
      qc.invalidateQueries({ queryKey: ['inbox', 'fact-conflicts-infinite'] })
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
    onSuccess: async (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['inbox', 'pending-types'] })
      if (vars.decision === 'approved') {
        try {
          await refreshBrowseTree({
            limit: 250,
            infer_mappings: true,
            auto_approve_mappings: true,
            llm_extract: false,
          })
        } catch {
          // Best-effort refresh; pending approval should still succeed.
        }
        qc.invalidateQueries({ queryKey: ['browse', 'tree'] })
      }
    },
  })
}
