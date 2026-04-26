import { Badge } from '@/components/ui/badge'
interface Props {
  type: string
}

export function EntityTypeBadge({ type }: Props) {
  return (
    <Badge variant="secondary" className="capitalize">
      {type.replace(/_/g, ' ')}
    </Badge>
  )
}
