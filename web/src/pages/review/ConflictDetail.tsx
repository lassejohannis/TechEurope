import { GitMerge } from 'lucide-react'

import { Skeleton } from '@/components/ui/skeleton'
import { Badge } from '@/components/ui/badge'
import { useEntityPairInbox, useFactConflictInbox } from '@/hooks/useConflicts'

interface Props {
  conflictId: string | null
  selectedClaimIndex: number | null
  onSelectClaim: (index: number) => void
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <Skeleton className="h-4 w-40" />
      <div className="grid grid-cols-1 gap-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    </div>
  )
}

function formatObject(fact: { object_id: string | null; object_literal: unknown }): string {
  if (fact.object_id) return fact.object_id
  if (fact.object_literal && typeof fact.object_literal === 'object') {
    return JSON.stringify(fact.object_literal)
  }
  return String(fact.object_literal ?? '—')
}

export default function ConflictDetail({ conflictId, selectedClaimIndex, onSelectClaim }: Props) {
  const facts = useFactConflictInbox('pending')
  const pairs = useEntityPairInbox('pending')

  if (!conflictId) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-8 text-center">
        <GitMerge className="size-8 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          Select a conflict from the inbox to see the competing facts and their evidence.
        </p>
      </div>
    )
  }

  if (facts.isPending || pairs.isPending) return <LoadingSkeleton />

  // ID prefix tells us which inbox we're looking at
  const isPair = conflictId.startsWith('pair:')
  const isFactConflict = conflictId.startsWith('fact:')
  const rawId = conflictId.replace(/^(pair|fact):/, '')

  if (isPair) {
    const item = pairs.data?.items.find((i) => i.id === rawId)
    if (!item) {
      return (
        <div className="p-4 text-sm text-muted-foreground">Pair not found.</div>
      )
    }
    return (
      <div className="flex flex-col gap-4 p-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Possible duplicate entities
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Two entities likely refer to the same real-world thing.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3">
          {[item.entity_1, item.entity_2].map((e, i) => {
            if (!e) return null
            const isSelected = selectedClaimIndex === i
            return (
              <button
                key={e.id}
                onClick={() => onSelectClaim(i)}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  isSelected ? 'border-primary bg-muted/40' : 'hover:bg-muted/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium">{e.canonical_name}</p>
                  <Badge variant="secondary" className="text-xs">{e.entity_type}</Badge>
                </div>
                <p className="mt-1 font-mono text-xs text-muted-foreground break-all">{e.id}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  Score: {String(item.resolution_signals?.score ?? '—')}
                </p>
              </button>
            )
          })}
        </div>
        <p className="font-mono text-xs text-muted-foreground break-all">
          resolution: {item.id}
        </p>
      </div>
    )
  }

  if (isFactConflict) {
    const item = facts.data?.items.find((i) => i.id === rawId)
    if (!item) {
      return (
        <div className="p-4 text-sm text-muted-foreground">Conflict not found.</div>
      )
    }
    return (
      <div className="flex flex-col gap-4 p-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Competing claims
          </p>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Predicate:{' '}
            <span className="font-medium capitalize">
              {item.facts[0]?.predicate.replace(/_/g, ' ') ?? '—'}
            </span>
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3">
          {item.facts.map((f, i) => {
            const isSelected = selectedClaimIndex === i
            return (
              <button
                key={f.id}
                onClick={() => onSelectClaim(i)}
                className={`rounded-lg border p-3 text-left transition-colors ${
                  isSelected ? 'border-primary bg-muted/40' : 'hover:bg-muted/30'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">Claim {String.fromCharCode(65 + i)}</p>
                  <Badge variant="outline" className="text-xs">
                    confidence {(f.confidence * 100).toFixed(0)}%
                  </Badge>
                </div>
                <p className="mt-2 text-sm">→ {formatObject(f)}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="secondary" className="text-xs">
                    {f.source?.source_type ?? 'unknown source'}
                  </Badge>
                  <span>{new Date(f.recorded_at).toLocaleDateString()}</span>
                </div>
                <p className="mt-1 font-mono text-[10px] text-muted-foreground break-all">{f.id}</p>
              </button>
            )
          })}
        </div>
        {item.rationale && (
          <p className="rounded-md border border-muted bg-muted/30 p-2 text-xs italic text-muted-foreground">
            {item.rationale}
          </p>
        )}
      </div>
    )
  }

  return (
    <div className="p-4 text-sm text-muted-foreground">
      Unknown conflict id: {conflictId}
    </div>
  )
}
