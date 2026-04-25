import { useQuery } from '@tanstack/react-query'
import { getFact } from '@/lib/api'
import type { ProvenanceResponse } from '@/types'

export function useFact(factId: string | null) {
  return useQuery<ProvenanceResponse>({
    queryKey: ['fact', factId],
    queryFn: () => getFact(factId!),
    enabled: !!factId,
  })
}
