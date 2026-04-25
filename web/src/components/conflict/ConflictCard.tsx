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
            <span className="font-medium">{fact.object === null ? '—' : String(fact.object)}</span>
          </div>
          <ConfidencePill confidence={fact.confidence} />
        </div>

        <div className="flex flex-wrap gap-1">
          {fact.derived_from.slice(0, 2).map((src) => (
            <Badge key={src} variant="outline" className="text-xs font-mono">
              {src.split(':')[0]}
            </Badge>
          ))}
          {fact.derived_from.length > 2 && (
            <Badge variant="outline" className="text-xs">
              +{fact.derived_from.length - 2}
            </Badge>
          )}
        </div>

        <p className="text-xs text-muted-foreground">
          Updated {new Date(fact.updated_at).toLocaleDateString()}
        </p>
      </CardContent>
    </Card>
  )
}
