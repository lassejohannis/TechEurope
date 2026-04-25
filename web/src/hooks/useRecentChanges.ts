import { useQuery } from '@tanstack/react-query'
import { listRecentChanges } from '@/lib/api'
import type { RecentChangesParams, ChangeEvent } from '@/types'

export function useRecentChanges(params: RecentChangesParams) {
  return useQuery<{ changes: ChangeEvent[]; cursor?: string }>({
    queryKey: ['changes', params],
    queryFn: () => listRecentChanges(params),
    staleTime: 10_000,
  })
}
