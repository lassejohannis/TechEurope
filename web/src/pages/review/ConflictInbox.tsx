import { useNavigate } from 'react-router-dom'
import { CheckCircle, AlertCircle, Users } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { useEntityPairInbox, useFactConflictInbox } from '@/hooks/useConflicts'
import { cn } from '@/lib/utils'

interface Props {
  selectedId: string | null
}

export default function ConflictInbox({ selectedId }: Props) {
  const navigate = useNavigate()
  const facts = useFactConflictInbox('pending')
  const pairs = useEntityPairInbox('pending')

  const factItems = facts.data?.items ?? []
  const pairItems = pairs.data?.items ?? []
  const factTotal = facts.data?.total ?? 0
  const pairTotal = pairs.data?.total ?? 0
  const total = factTotal + pairTotal
  const loading = facts.isPending || pairs.isPending

  return (
    <div className="flex flex-col">
      <div className="border-b px-3 py-2">
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
      </div>

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

      {!loading && factItems.length > 0 && (
        <>
          <p className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Fact conflicts
            {factTotal > factItems.length && ` (showing ${factItems.length}/${factTotal})`}
          </p>
          <ul className="flex flex-col">
            {factItems.map((item) => {
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
        </>
      )}

      {!loading && pairItems.length > 0 && (
        <>
          <p className="px-3 pt-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Entity pairs (possible duplicates)
            {pairTotal > pairItems.length && ` (showing ${pairItems.length}/${pairTotal})`}
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
        </>
      )}
    </div>
  )
}
