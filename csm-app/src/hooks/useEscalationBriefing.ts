import { useQuery } from '@tanstack/react-query'
import { generateEscalationBriefing } from '@/lib/api'

export function useEscalationBriefing(accountId: string | null) {
  return useQuery({
    queryKey: ['escalation', accountId],
    queryFn: () => generateEscalationBriefing(accountId!),
    enabled: accountId !== null,
    staleTime: Infinity,
    retry: 1,
  })
}
