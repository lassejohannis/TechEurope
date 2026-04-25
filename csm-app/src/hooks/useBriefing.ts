import { useQuery } from '@tanstack/react-query'
import { getDailyBriefing } from '@/lib/api'

export function useBriefing() {
  return useQuery({
    queryKey: ['briefing', 'daily'],
    queryFn: getDailyBriefing,
    staleTime: 60_000,
    retry: 1,
  })
}
