import { useQuery } from '@tanstack/react-query'
import { searchMemory } from '@/lib/api'
import type { SearchParams, SearchResult } from '@/types'

export function useSearch(params: SearchParams | null) {
  return useQuery<SearchResult>({
    queryKey: ['search', params],
    queryFn: () => searchMemory(params!),
    enabled: !!params && params.query.trim().length > 0,
  })
}
