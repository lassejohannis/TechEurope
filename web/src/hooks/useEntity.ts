import { useQuery } from '@tanstack/react-query'
import { getEntity } from '@/lib/api'
import type { EntityCard } from '@/types'

export function useEntity(entityId: string | null) {
  return useQuery<EntityCard>({
    queryKey: ['entity', entityId],
    queryFn: () => getEntity(entityId!),
    enabled: !!entityId,
  })
}
