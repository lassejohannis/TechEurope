import { useQuery } from '@tanstack/react-query'
import { generateRecoveryEmail } from '@/lib/api'

export function useRecoveryEmail(accountId: string | null, variation: number = 0) {
  return useQuery({
    queryKey: ['recovery-email', accountId, variation],
    queryFn: () => generateRecoveryEmail(accountId!, variation),
    enabled: accountId !== null,
    staleTime: Infinity,
    retry: 1,
  })
}
