import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, confidenceClass, confidenceLevel } from '@/lib/utils'

interface Props {
  confidence: number
  className?: string
}

export function ConfidencePill({ confidence, className }: Props) {
  const level = confidenceLevel(confidence)
  const label = level === 'high'
    ? 'High'
    : level === 'medium'
      ? 'Medium'
      : level === 'low'
        ? 'Low'
        : 'Very low'

  return (
    <Tooltip>
      <TooltipTrigger
        render={
          <span
            className={cn(
              'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium tabular-nums',
              confidenceClass(confidence),
              className,
            )}
          >
            {label}
          </span>
        }
      />
      <TooltipContent>
        Confidence: {level} ({confidence.toFixed(3)})
      </TooltipContent>
    </Tooltip>
  )
}
