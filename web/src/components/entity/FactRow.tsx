import { Badge } from '@/components/ui/badge'
import { ConfidencePill } from './ConfidencePill'
import { cn } from '@/lib/utils'
import type { Fact } from '@/types'

interface Props {
  fact: Fact
  onFlag?: (fact: Fact) => void
}

const STATUS_CLASSES: Record<Fact['status'], string> = {
  live: '',
  active: '',
  draft: 'opacity-60',
  superseded: 'opacity-40 line-through',
  disputed: 'border-l-2 border-destructive pl-2',
  invalidated: 'opacity-30 line-through',
  needs_refresh: 'opacity-60 italic',
}

export function FactRow({ fact, onFlag }: Props) {
  const valueStr =
    fact.object_literal != null ? String(fact.object_literal) : fact.object_id ?? '—'

  return (
    <div
      className={cn(
        'flex items-start justify-between gap-3 py-2 text-sm',
        STATUS_CLASSES[fact.status],
      )}
    >
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="font-medium text-muted-foreground capitalize">
          {fact.predicate.replace(/_/g, ' ')}
        </span>
        <span className="text-foreground">{valueStr}</span>
      </div>

      <div className="flex shrink-0 items-center gap-1.5">
        {fact.status === 'disputed' && (
          <Badge variant="destructive" className="text-xs">conflict</Badge>
        )}
        <ConfidencePill confidence={fact.confidence} />
        {onFlag && (
          <button
            onClick={() => onFlag(fact)}
            className="text-xs text-muted-foreground hover:text-destructive transition-colors"
            aria-label="Flag this fact"
          >
            Flag
          </button>
        )}
      </div>
    </div>
  )
}
