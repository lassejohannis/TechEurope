import { useQuery } from '@tanstack/react-query'
import { getCardSummaries } from '@/lib/api'

export function useCardSummaries() {
  return useQuery({
    queryKey: ['card-summaries'],
    queryFn: getCardSummaries,
    staleTime: 60_000,
    retry: 1,
  })
}
