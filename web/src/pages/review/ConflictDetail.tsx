import { GitMerge } from 'lucide-react'
import { ConflictCard } from '@/components/conflict/ConflictCard'
import { useFact } from '@/hooks/useFact'
import { Skeleton } from '@/components/ui/skeleton'

interface Props {
  conflictId: string | null
  selectedClaimIndex: number | null
  onSelectClaim: (index: number) => void
}

function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-4 p-4">
      <Skeleton className="h-4 w-40" />
      <div className="grid grid-cols-2 gap-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
    </div>
  )
}

export default function ConflictDetail({ conflictId, selectedClaimIndex, onSelectClaim }: Props) {
  const { data, isLoading } = useFact(conflictId)

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

  if (isLoading) return <LoadingSkeleton />

  // When backend is down, show a placeholder with the conflict ID
  const primaryFact = data?.fact
  const conflicts = data?.conflicts ?? []
  const allFacts = primaryFact ? [primaryFact, ...conflicts] : []

  if (allFacts.length === 0) {
    return (
      <div className="flex flex-col gap-4 p-4">
        <p className="text-sm text-muted-foreground">
          Backend not yet available. Conflict details will show here once the API is live.
        </p>
        <p className="font-mono text-xs text-muted-foreground break-all">{conflictId}</p>
      </div>
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
            {(primaryFact ?? allFacts[0]).predicate.replace(/_/g, ' ')}
          </span>
        </p>
      </div>

      <div className="grid grid-cols-1 gap-3">
        {allFacts.map((fact, i) => (
          <ConflictCard
            key={fact.id}
            label={`Claim ${String.fromCharCode(65 + i)}`}
            fact={fact}
            isSelected={selectedClaimIndex === i}
            onSelect={() => onSelectClaim(i)}
          />
        ))}
      </div>

      {data?.provenance && data.provenance.length > 0 && (
        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Provenance
          </p>
          {data.provenance.map((p) => (
            <div key={p.source_record_id} className="rounded-md border p-2 text-xs">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-muted-foreground truncate">{p.source_record_id}</span>
                <span className="shrink-0 capitalize text-muted-foreground">{p.extractor}</span>
              </div>
              {p.evidence_snippet && (
                <p className="mt-1 text-muted-foreground italic">"{p.evidence_snippet}"</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
