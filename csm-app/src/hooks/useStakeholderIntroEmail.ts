import { useQuery } from '@tanstack/react-query'
import { generateStakeholderIntroEmail } from '@/lib/api'

export function useStakeholderIntroEmail(accountId: string | null, contactId: string | null) {
  return useQuery({
    queryKey: ['stakeholder-intro', accountId, contactId],
    queryFn: () => generateStakeholderIntroEmail(accountId!, contactId!),
    enabled: accountId !== null && contactId !== null,
    staleTime: Infinity,
    retry: 1,
  })
}
