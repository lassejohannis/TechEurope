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
  invalidated: 'opacity-40 line-through',
  needs_refresh: 'opacity-60',
}

function displayValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    return value.map((v) => displayValue(v)).join(', ')
  }
  if (typeof value === 'object') {
    const obj = value as Record<string, unknown>
    for (const key of ['canonical_name', 'name', 'title', 'label', 'value']) {
      if (typeof obj[key] === 'string' && obj[key]) return obj[key]
    }
    try {
      const json = JSON.stringify(obj)
      return json.length > 120 ? `${json.slice(0, 117)}...` : json
    } catch {
      return 'structured value'
    }
  }
  return String(value)
}

function sourceLabel(sourceId: string): string {
  const [prefix] = sourceId.split(':')
  return prefix || 'unknown'
}

export function FactRow({ fact, onFlag }: Props) {
  const rawValue = fact.object_literal ?? fact.object_id
  const valueStr = displayValue(rawValue)

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
        <span className="text-foreground break-words">{valueStr}</span>
        <span className="text-[11px] text-muted-foreground">
          Source: {sourceLabel(fact.source_id)}
        </span>
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
