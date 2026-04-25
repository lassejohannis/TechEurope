import { useQuery } from '@tanstack/react-query'
import { searchMemory } from '@/lib/api'
import type { SearchParams, SearchResponse } from '@/types'

export function useSearch(params: SearchParams | null) {
  return useQuery<SearchResponse>({
    queryKey: ['search', params],
    queryFn: () => searchMemory(params!),
    enabled: !!params && params.query.trim().length > 0,
  })
}
