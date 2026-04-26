import { useNavigate } from 'react-router-dom'
import { CheckCircle, AlertCircle, Users } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useEntityPairInboxInfinite, useFactConflictInboxInfinite } from '@/hooks/useConflicts'
import { cn } from '@/lib/utils'

interface Props {
  selectedId: string | null
}

export default function ConflictInbox({ selectedId }: Props) {
  const navigate = useNavigate()
  const facts = useFactConflictInboxInfinite('pending', 100)
  const pairs = useEntityPairInboxInfinite('pending', 100)
  const [search, setSearch] = useState('')
  const [groupMode, setGroupMode] = useState(true)

  const factItems = useMemo(
    () => facts.data?.pages.flatMap((p) => p.items) ?? [],
    [facts.data?.pages],
  )
  const pairItems = useMemo(
    () => pairs.data?.pages.flatMap((p) => p.items) ?? [],
    [pairs.data?.pages],
  )
  const factTotal = facts.data?.pages[0]?.total ?? 0
  const pairTotal = pairs.data?.pages[0]?.total ?? 0
  const total = factTotal + pairTotal
  const loading = facts.isPending || pairs.isPending
  const query = search.trim().toLowerCase()

  const filteredFactItems = useMemo(() => {
    if (!query) return factItems
    return factItems.filter((item) => {
      const first = item.facts[0]
      const predicate = String(first?.predicate ?? '').toLowerCase()
      const subject = String(first?.subject_id ?? '').toLowerCase()
      const object = String(first?.object_literal ?? first?.object_id ?? '').toLowerCase()
      return predicate.includes(query) || subject.includes(query) || object.includes(query)
    })
  }, [factItems, query])

  const groupedFactItems = useMemo(() => {
    const groups = new Map<string, { id: string; subjectId: string; predicate: string; count: number }>()
    for (const item of filteredFactItems) {
      const first = item.facts[0]
      if (!first) continue
      const key = `${first.subject_id}::${first.predicate}`
      const existing = groups.get(key)
      if (existing) {
        existing.count += 1
      } else {
        groups.set(key, {
          id: item.id,
          subjectId: first.subject_id,
          predicate: first.predicate,
          count: 1,
        })
      }
    }
    return [...groups.values()].sort((a, b) => b.count - a.count)
  }, [filteredFactItems])

  const loadedFactCount = factItems.length
  const loadedPairCount = pairItems.length
  const hasMoreFacts = loadedFactCount < factTotal
  const hasMorePairs = loadedPairCount < pairTotal

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-b px-3 py-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Conflict Inbox
          </p>
          {total > 0 && (
            <Badge variant="destructive" className="text-xs">
              {total}
            </Badge>
          )}
        </div>
        <div className="mt-2 flex items-center gap-2">
          <input
            type="text"
            placeholder="Filter conflicts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-8 flex-1 rounded-md border bg-background px-2 text-xs"
          />
          <Button size="sm" variant={groupMode ? 'default' : 'outline'} onClick={() => setGroupMode((v) => !v)}>
            {groupMode ? 'Grouped' : 'Flat'}
          </Button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {loading && (
          <p className="px-3 py-6 text-sm text-muted-foreground">Loading…</p>
        )}

        {!loading && total === 0 && (
          <div className="flex flex-col items-center gap-2 p-6 text-center">
            <CheckCircle className="size-6 text-muted-foreground/40" />
            <p className="text-sm text-muted-foreground">
              No conflicts to review. Conflicts appear here when two sources
              disagree on the same fact, or when an entity might already exist.
            </p>
          </div>
        )}

        {!loading && filteredFactItems.length > 0 && (
          <>
            <p className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Fact conflicts
              {factTotal > loadedFactCount && ` (loaded ${loadedFactCount}/${factTotal})`}
            </p>
            {groupMode ? (
              <ul className="flex flex-col">
                {groupedFactItems.map((group) => {
                  const id = `fact:${group.id}`
                  const isActive = selectedId === id
                  return (
                    <li key={`${group.subjectId}:${group.predicate}`}>
                      <button
                        onClick={() => navigate(`/review/${encodeURIComponent(id)}`)}
                        className={cn(
                          'flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors hover:bg-muted/50',
                          isActive && 'bg-muted',
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium capitalize">
                            {group.predicate.replace(/_/g, ' ')}
                          </span>
                          <Badge variant="destructive" className="text-xs shrink-0">
                            {group.count} conflicts
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground font-mono truncate">
                          {group.subjectId}
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            ) : (
              <ul className="flex flex-col">
                {filteredFactItems.map((item) => {
                  const id = `fact:${item.id}`
                  const isActive = selectedId === id
                  const firstFact = item.facts[0]
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => navigate(`/review/${encodeURIComponent(id)}`)}
                        className={cn(
                          'flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors hover:bg-muted/50',
                          isActive && 'bg-muted',
                        )}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-sm font-medium capitalize">
                            {firstFact?.predicate.replace(/_/g, ' ') ?? 'unknown'}
                          </span>
                          <Badge variant="destructive" className="text-xs shrink-0">
                            <AlertCircle className="mr-1 size-3" />
                            conflict
                          </Badge>
                        </div>
                        <span className="text-xs text-muted-foreground font-mono truncate">
                          {firstFact?.subject_id ?? '—'}
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {item.facts.length} sources
                        </span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            )}
            {hasMoreFacts && (
              <div className="px-3 py-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full"
                  disabled={facts.isFetchingNextPage}
                  onClick={() => facts.fetchNextPage()}
                >
                  {facts.isFetchingNextPage ? 'Loading more…' : 'Load more fact conflicts'}
                </Button>
              </div>
            )}
          </>
        )}

        {!loading && pairItems.length > 0 && (
          <>
            <p className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Entity pairs (possible duplicates)
              {pairTotal > loadedPairCount && ` (loaded ${loadedPairCount}/${pairTotal})`}
            </p>
            <ul className="flex flex-col">
              {pairItems.map((item) => {
                const id = `pair:${item.id}`
                const isActive = selectedId === id
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => navigate(`/review/${encodeURIComponent(id)}`)}
                      className={cn(
                        'flex w-full flex-col gap-1 px-3 py-3 text-left transition-colors hover:bg-muted/50',
                        isActive && 'bg-muted',
                      )}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium truncate">
                          {item.entity_1?.canonical_name ?? '?'}
                        </span>
                        <Badge variant="secondary" className="text-xs shrink-0">
                          <Users className="mr-1 size-3" />
                          pair
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground truncate">
                        vs {item.entity_2?.canonical_name ?? '?'}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        {new Date(item.created_at).toLocaleDateString()}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>
            {hasMorePairs && (
              <div className="px-3 py-2">
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full"
                  disabled={pairs.isFetchingNextPage}
                  onClick={() => pairs.fetchNextPage()}
                >
                  {pairs.isFetchingNextPage ? 'Loading more…' : 'Load more entity pairs'}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
