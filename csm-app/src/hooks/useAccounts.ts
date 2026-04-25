import { useQuery } from '@tanstack/react-query'
import { listAccounts } from '@/lib/api'

export function useAccounts() {
  return useQuery({
    queryKey: ['accounts'],
    queryFn: listAccounts,
    staleTime: 60_000,
    retry: 1,
  })
}
