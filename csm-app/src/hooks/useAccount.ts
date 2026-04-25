import { useQuery } from '@tanstack/react-query'
import { getAccountCard } from '@/lib/api'

export function useAccount(accountId: string | null) {
  return useQuery({
    queryKey: ['account', accountId],
    queryFn: () => getAccountCard(accountId!),
    enabled: accountId !== null,
    staleTime: 30_000,
    retry: 1,
  })
}
