import { useQuery } from '@tanstack/react-query'
import { getFact } from '@/lib/api'
import type { ProvenanceHistory } from '@/types'

export function useFact(factId: string | null) {
  return useQuery<ProvenanceHistory>({
    queryKey: ['fact', factId],
    queryFn: () => getFact(factId!),
    enabled: !!factId,
  })
}
