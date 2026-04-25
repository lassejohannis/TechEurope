import { useQuery } from '@tanstack/react-query'
import { getAccountInsights } from '@/lib/api'

export function useAccountInsights(accountId: string | null) {
  return useQuery({
    queryKey: ['account-insights', accountId],
    queryFn: () => getAccountInsights(accountId!),
    enabled: accountId !== null,
    staleTime: 30_000,
    retry: 1,
  })
}
