import { Badge } from '@/components/ui/badge'
import type { EntityType } from '@/types'

interface Props {
  type: EntityType
}

export function EntityTypeBadge({ type }: Props) {
  return (
    <Badge variant="secondary" className="capitalize">
      {type.replace(/_/g, ' ')}
    </Badge>
  )
}
