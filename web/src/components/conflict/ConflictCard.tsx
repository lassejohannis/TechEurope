import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { ConfidencePill } from '@/components/entity/ConfidencePill'
import type { Fact } from '@/types'

interface Props {
  label: string
  fact: Fact
  isSelected?: boolean
  onSelect?: () => void
}

export function ConflictCard({ label, fact, isSelected, onSelect }: Props) {
  const rawValue = fact.object_literal ?? fact.object_id
  const sourceParts = fact.source_id ? fact.source_id.split(':') : []
  return (
    <Card
      className={`cursor-pointer transition-all ${isSelected ? 'ring-2 ring-primary' : 'hover:border-primary/50'}`}
      onClick={onSelect}
    >
      <CardHeader className="pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{label}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2">
        <div className="flex items-start justify-between gap-2">
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-muted-foreground capitalize">
              {fact.predicate.replace(/_/g, ' ')}
            </span>
            <span className="font-medium">{rawValue == null ? '—' : String(rawValue)}</span>
          </div>
          <ConfidencePill confidence={fact.confidence} />
        </div>

        <div className="flex flex-wrap gap-1">
          {sourceParts.length > 0 && (
            <Badge variant="outline" className="text-xs font-mono">
              {sourceParts[0]}
            </Badge>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Updated {new Date(fact.recorded_at).toLocaleDateString()}
        </p>
      </CardContent>
    </Card>
  )
}
