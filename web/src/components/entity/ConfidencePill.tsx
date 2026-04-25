import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn, confidenceClass, confidenceLevel } from '@/lib/utils'

interface Props {
  confidence: number
  className?: string
}

export function ConfidencePill({ confidence, className }: Props) {
  const pct = Math.round(confidence * 100)
  const level = confidenceLevel(confidence)

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          className={cn(
            'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium tabular-nums',
            confidenceClass(confidence),
            className,
          )}
        >
          {pct}%
        </span>
      </TooltipTrigger>
      <TooltipContent>
        Confidence: {level} ({confidence.toFixed(3)})
      </TooltipContent>
    </Tooltip>
  )
}
